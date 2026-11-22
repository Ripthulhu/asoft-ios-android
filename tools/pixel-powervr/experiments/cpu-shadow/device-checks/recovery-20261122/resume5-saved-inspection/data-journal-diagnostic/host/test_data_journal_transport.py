"""Exercise only local staging/launch guards with a non-executable fixture.

No diagnostic, image tool or device process is started.  The tested transfer
programs are remapped into a temporary directory by replacing their one BASE
path literal.  The two root-owner comparisons are translated to the invoking
local UID for these temporary files only; generated phone programs retain UID 0.
"""
from contextlib import redirect_stdout
import ast
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('data_journal_transport_under_test', HERE / 'build_data_journal_transport.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
PARSER_FIXTURE = b"raise RuntimeError('parser fixture execution is forbidden during staging')\n"
PARSER_PIN = {'bytes': len(PARSER_FIXTURE), 'sha256': hashlib.sha256(PARSER_FIXTURE).hexdigest()}
FIXTURE = ('PARSER_SOURCE_PIN = ' + repr(PARSER_PIN) + "\nraise RuntimeError('fixture execution is forbidden during source staging')\n").encode()


class ExclusiveTransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='data-journal-transport-test-')
        self.root = Path(self.temp.name)
        self.packet = self.root / 'packet'
        self.packet.mkdir()
        (self.packet / 'inspect_data_journal.py').write_bytes(FIXTURE)
        (self.root / 'parse_data_journal.py').write_bytes(PARSER_FIXTURE)
        self.original_root = builder.ROOT
        builder.ROOT = self.packet
        try:
            self.record = builder.build(len(FIXTURE), hashlib.sha256(FIXTURE).hexdigest(), len(PARSER_FIXTURE), PARSER_PIN['sha256'])
        finally:
            builder.ROOT = self.original_root
        self.phone = self.root / 'phone'
        self.phone.mkdir()
        self.transfer = self.phone / builder.TRANSFER_NAME
        self.source = self.phone / builder.PHONE_NAME
        self.parser_source = self.phone / builder.PARSER_NAME
        self.output = self.phone / builder.OUTPUT_NAME
        self.receipt = self.phone / builder.INSTALL_NAME
        self.steps = json.loads((self.packet / 'transport-steps.json').read_text())

    def tearDown(self):
        self.temp.cleanup()

    def execute(self, path):
        tree = ast.parse(path.read_bytes())

        class RemapBase(ast.NodeTransformer):
            count = 0
            uid_count = 0

            def visit_Constant(this, node):
                if node.value == builder.BASE:
                    this.count += 1
                    return ast.copy_location(ast.Constant(str(self.phone)), node)
                return node

            def visit_Compare(this, node):
                node = this.generic_visit(node)
                root_test = (isinstance(node.left, ast.Call) and
                             isinstance(node.left.func, ast.Attribute) and
                             isinstance(node.left.func.value, ast.Name) and
                             node.left.func.value.id == 'os' and node.left.func.attr == 'geteuid')
                owner_test = isinstance(node.left, ast.Attribute) and node.left.attr == 'st_uid'
                if root_test or owner_test:
                    self.assertEqual(len(node.comparators), 1)
                    self.assertIsInstance(node.comparators[0], ast.Constant)
                    self.assertEqual(node.comparators[0].value, 0)
                    this.uid_count += 1
                    node.comparators[0] = ast.copy_location(ast.Constant(os.geteuid()), node.comparators[0])
                return node

        remapper = RemapBase()
        tree = ast.fix_missing_locations(remapper.visit(tree))
        self.assertEqual(remapper.count, 1)
        self.assertEqual(remapper.uid_count, 2)
        with redirect_stdout(io.StringIO()):
            exec(compile(tree, str(path), 'exec'), {'__name__': '__main__'})

    def step(self, index):
        self.execute(self.packet / 'source-transfer' / (self.steps[index]['name'] + '.py'))

    def stage_chunks(self):
        for index in range(len(self.steps) - 1):
            self.step(index)

    def install(self):
        for index in range(len(self.steps)):
            self.step(index)

    def launch(self):
        self.execute(self.packet / 'launch_data_journal_diagnostic.py')

    def test_install_retains_exact_source_without_executing_it(self):
        self.install()
        self.assertEqual(self.source.read_bytes(), FIXTURE)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.parser_source.read_bytes(),PARSER_FIXTURE)
        receipt = json.loads(self.receipt.read_text())
        self.assertIs(receipt['execution_started'], False)
        self.assertEqual(receipt['files'], [{'path': builder.PHONE_NAME, 'bytes': len(FIXTURE),
                                             'sha256': hashlib.sha256(FIXTURE).hexdigest()},
                                            {'path': builder.PARSER_NAME, **PARSER_PIN}])
        self.assertEqual({p.name for p in self.phone.iterdir()},
                         {builder.PHONE_NAME, builder.PARSER_NAME, builder.INSTALL_NAME, builder.TRANSFER_NAME})

    def test_existing_source_refused_before_transfer_directory(self):
        self.source.write_bytes(b'preserved source')
        with self.assertRaisesRegex(ValueError, 'target already exists'):
            self.step(0)
        self.assertEqual(self.source.read_bytes(), b'preserved source')
        self.assertFalse(self.transfer.exists())

    def test_existing_parser_refused_before_transfer_directory(self):
        self.parser_source.write_bytes(b'preserved parser')
        with self.assertRaisesRegex(ValueError, 'target already exists'):
            self.step(0)
        self.assertEqual(self.parser_source.read_bytes(),b'preserved parser')
        self.assertFalse(self.transfer.exists())

    def test_existing_output_refused_before_transfer_directory(self):
        self.output.mkdir()
        (self.output / 'preserved').write_bytes(b'evidence')
        with self.assertRaisesRegex(ValueError, 'target already exists'):
            self.step(0)
        self.assertFalse(self.transfer.exists())
        self.assertEqual((self.output / 'preserved').read_bytes(), b'evidence')

    def test_duplicate_chunk_and_assembly_cannot_overwrite(self):
        self.stage_chunks()
        before = (self.transfer / 'chunk-00').read_bytes()
        with self.assertRaises(FileExistsError):
            self.step(1)
        self.assertEqual((self.transfer / 'chunk-00').read_bytes(), before)
        self.step(-1)
        before_source, before_receipt = self.source.read_bytes(), self.receipt.read_bytes()
        with self.assertRaisesRegex(ValueError, 'already assembled or unknown files'):
            self.step(-1)
        self.assertEqual(self.source.read_bytes(), before_source)
        self.assertEqual(self.receipt.read_bytes(), before_receipt)

    def test_new_target_between_begin_and_assembly_is_preserved(self):
        self.stage_chunks()
        self.source.write_bytes(b'new preserved source')
        with self.assertRaisesRegex(ValueError, 'target already exists'):
            self.step(-1)
        self.assertEqual(self.source.read_bytes(), b'new preserved source')
        self.assertFalse(self.receipt.exists())
        self.assertFalse((self.transfer / 'install-reserved.json').exists())

    def test_corrupt_chunk_refuses_before_installation(self):
        self.stage_chunks()
        chunk = self.transfer / 'chunk-00'
        body = chunk.read_bytes()
        chunk.write_bytes(bytes([body[0] ^ 1]) + body[1:])
        with self.assertRaisesRegex(ValueError, 'stored chunk differs'):
            self.step(-1)
        self.assertFalse(self.source.exists())
        self.assertFalse(self.receipt.exists())

    def test_unknown_transfer_entry_refuses_before_installation(self):
        self.stage_chunks()
        (self.transfer / 'unknown').write_bytes(b'preserved')
        with self.assertRaisesRegex(ValueError, 'unknown files'):
            self.step(-1)
        self.assertFalse(self.source.exists())

    def test_symlink_chunk_refuses_before_installation(self):
        self.stage_chunks()
        chunk = self.transfer / 'chunk-00'
        outside = self.root / 'outside'
        outside.write_bytes(chunk.read_bytes())
        chunk.unlink()
        chunk.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'noncanonical transfer path'):
            self.step(-1)
        self.assertFalse(self.source.exists())

    def test_launch_refuses_occupied_output_without_execution(self):
        self.install()
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError, 'preserve existing diagnostic output'):
            self.launch()

    def test_launch_refuses_modified_source_without_execution(self):
        self.install()
        self.source.write_bytes(FIXTURE.replace(b'RuntimeError', b'RuntimeErr0r'))
        with self.assertRaisesRegex(ValueError, 'installed source pair differs'):
            self.launch()
        self.assertFalse(self.output.exists())

    def test_launch_refuses_modified_parser_without_execution(self):
        self.install()
        self.parser_source.write_bytes(PARSER_FIXTURE.replace(b'RuntimeError',b'RuntimeErr0r'))
        with self.assertRaisesRegex(ValueError,'installed source pair differs'):
            self.launch()
        self.assertFalse(self.output.exists())

    def test_launch_refuses_modified_install_receipt_without_execution(self):
        self.install()
        receipt = json.loads(self.receipt.read_text())
        receipt['execution_started'] = True
        self.receipt.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, 'source installation receipt differs'):
            self.launch()
        self.assertFalse(self.output.exists())

    def test_builder_refuses_changed_frozen_source_before_outputs(self):
        fresh = self.root / 'fresh'
        fresh.mkdir()
        (fresh / 'inspect_data_journal.py').write_bytes(FIXTURE)
        builder.ROOT = fresh
        try:
            with self.assertRaisesRegex(AssertionError, 'frozen source pin differs'):
                builder.build(len(FIXTURE), '0' * 64, len(PARSER_FIXTURE), PARSER_PIN['sha256'])
        finally:
            builder.ROOT = self.original_root
        self.assertEqual([p.name for p in fresh.iterdir()], ['inspect_data_journal.py'])


if __name__ == '__main__':
    unittest.main()
