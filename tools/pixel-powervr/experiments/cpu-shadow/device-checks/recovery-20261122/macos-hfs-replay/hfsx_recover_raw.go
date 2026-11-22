// hfsx-recover-raw runs the pinned portable HFS+ recovery on a private raw copy.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"

	"github.com/deploymenttheory/go-apfs-v3/block"
	"github.com/deploymenttheory/go-apfs-v3/hfsplus"
)

func recoverRaw(ctx context.Context, input, output string) (hfsplus.JournalReplayReport, error) {
	var report hfsplus.JournalReplayReport
	info, err := os.Lstat(input)
	if err != nil {
		return report, err
	}
	if !info.Mode().IsRegular() {
		return report, errors.New("input must be a regular raw HFS image")
	}
	if _, err := os.Lstat(output); err == nil {
		return report, errors.New("output already exists")
	} else if !errors.Is(err, os.ErrNotExist) {
		return report, err
	}

	source, err := block.Open(input)
	if err != nil {
		return report, err
	}
	defer source.Close()
	before, err := hfsplus.InspectJournal(source)
	if err != nil {
		return report, err
	}
	if !before.Pending {
		return report, errors.New("input has no pending HFS journal")
	}
	if _, err = hfsplus.ValidateJournalReplay(ctx, source); err != nil {
		return report, err
	}

	dir := filepath.Dir(output)
	stage, err := block.Stage(ctx, source, dir)
	if err != nil {
		return report, err
	}
	defer stage.Close()
	report, err = hfsplus.RecoverJournal(ctx, stage)
	if err != nil {
		return report, err
	}
	if err = stage.Sync(); err != nil {
		return report, err
	}

	tmp, err := os.CreateTemp(dir, ".hfsx-recovered-*")
	if err != nil {
		return report, err
	}
	defer os.Remove(tmp.Name())
	size, err := io.Copy(tmp, io.NewSectionReader(stage, 0, stage.Size()))
	if err != nil {
		tmp.Close()
		return report, err
	}
	if size != stage.Size() {
		tmp.Close()
		return report, io.ErrShortWrite
	}
	if err := errors.Join(tmp.Sync(), tmp.Close(), ctx.Err()); err != nil {
		return report, err
	}
	if err = os.Link(tmp.Name(), output); err != nil {
		return report, err
	}
	dirHandle, err := os.Open(dir)
	if err != nil {
		return report, fmt.Errorf("output published but directory sync unavailable: %w", err)
	}
	defer dirHandle.Close()
	if err = dirHandle.Sync(); err != nil {
		return report, fmt.Errorf("output published but directory sync failed: %w", err)
	}
	return report, nil
}

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: hfsx-recover-raw INPUT.raw NEW-OUTPUT.raw")
		os.Exit(2)
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	report, err := recoverRaw(ctx, os.Args[1], os.Args[2])
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := json.NewEncoder(os.Stdout).Encode(report); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
