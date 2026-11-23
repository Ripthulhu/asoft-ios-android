//! Exercises the public render encoder with a real XR fetch and a readback attachment.
use std::error::Error;
use std::time::Duration;

use metal2vulkan::device::ApiVersion;
use metal2vulkan::metal::{ColorWriteMask, PixelFormat, PrimitiveType, TextureUsage};
use metal2vulkan::pipeline::{ColorAttachmentDescriptor, RenderPipelineDescriptor, StageSource};
use metal2vulkan_runtime::{
    BlitOption, ClearColor, CommandBufferStatus, Device, DeviceOptions, LoadAction, Origin,
    PipelineOptions, RenderPassDescriptor, ResourceOptions, Size, StoreAction, TextureDescriptor,
};

fn main() -> Result<(), Box<dyn Error>> {
    const SIDE: u64 = 16;
    let air = std::fs::read(
        std::env::args_os()
            .nth(1)
            .ok_or("pass the assembled AIR fixture")?,
    )?;
    let mut options = DeviceOptions::default();
    options.instance_api_version = Some(ApiVersion::V1_3);
    let device = Device::system_default_with(&options)?;
    println!("Running XR render-pass test on {}", device.name());
    let libs = metal2vulkan::library::Library::from_air(&air)?;
    let library = device.new_library_with_compile_library(libs);
    let vertex = library.new_function_with_name("xr_vertex")?;
    let fragment = library.new_function_with_name("xr_fragment")?;

    if let Some(path) = std::env::args_os().nth(2) {
        let entry = std::env::args()
            .nth(3)
            .ok_or("pass the replay entry name")?;
        let bytes = std::fs::read(path)?;
        let replay = if bytes.starts_with(b"MTLB") {
            device.new_library_with_data(&bytes)?
        } else {
            device
                .new_library_with_compile_library(metal2vulkan::library::Library::from_air(&bytes)?)
        };
        let fragment = replay.new_function_with_name(&entry)?;
        let mut pipeline =
            RenderPipelineDescriptor::new(StageSource::Function(vertex.function_descriptor()));
        pipeline.fragment = Some(StageSource::Function(fragment.function_descriptor()));
        for (index, format, mask) in [
            (0, PixelFormat::RGB10A82PXR10, ColorWriteMask::ALL),
            (1, PixelFormat::RG16Float, ColorWriteMask::NONE),
            (2, PixelFormat::RGB10A82PXR10, ColorWriteMask::NONE),
        ] {
            let mut attachment = ColorAttachmentDescriptor::new(format);
            attachment.write_mask = mask;
            pipeline.color_attachments[index] = Some(attachment);
        }
        pipeline.depth_format = Some(PixelFormat::Depth32FloatStencil8);
        pipeline.stencil_format = Some(PixelFormat::Depth32FloatStencil8);
        device.new_render_pipeline_state(&pipeline, &PipelineOptions::default())?;
        println!("Replay pipeline {entry} compiled");
        return Ok(());
    }

    let xr_format = PixelFormat::RGB10A82PXR10;
    let witness_format = PixelFormat::RGBA32Float;
    let mut pipeline =
        RenderPipelineDescriptor::new(StageSource::Function(vertex.function_descriptor()));
    pipeline.fragment = Some(StageSource::Function(fragment.function_descriptor()));
    pipeline.color_attachments[0] = Some(ColorAttachmentDescriptor::new(xr_format));
    pipeline.color_attachments[1] = Some(ColorAttachmentDescriptor::new(witness_format));
    let pipeline = device.new_render_pipeline_state(&pipeline, &PipelineOptions::default())?;

    let texture = |format| {
        let mut descriptor = TextureDescriptor::texture_2d(format, SIDE, SIDE, false);
        descriptor.usage = TextureUsage::RENDER_TARGET;
        descriptor.resource_options = ResourceOptions::private();
        device.new_texture(&descriptor)
    };
    let xr = texture(xr_format)?;
    let witness = texture(witness_format)?;
    let queue = device.new_command_queue()?;
    let row = SIDE * 16;
    let bytes = row * SIDE;
    let readback = device.new_buffer(bytes, ResourceOptions::shared())?;

    let mut pass = RenderPassDescriptor::new();
    pass.color_attachments[0].texture = Some(xr);
    pass.color_attachments[0].store_action = StoreAction::Store;
    pass.color_attachments[0].clear_color = ClearColor::new(0.5, 0.125, -0.125, 1.0);
    pass.color_attachments[1].texture = Some(witness.clone());
    pass.color_attachments[1].load_action = LoadAction::Clear;
    pass.color_attachments[1].store_action = StoreAction::Store;

    for (load, draws, expected) in [
        (LoadAction::Clear, 3, 0.5009765625_f32),
        (LoadAction::Load, 1, 0.501953125_f32),
    ] {
        pass.color_attachments[0].load_action = load;
        let cb = queue.command_buffer()?;
        let mut render = cb.render_command_encoder(&pass)?;
        render.set_render_pipeline_state(&pipeline)?;
        for _ in 0..draws {
            render.draw_primitives(PrimitiveType::Triangle, 0, 3, 1, 0)?;
        }
        render.end_encoding()?;
        let mut blit = cb.blit_command_encoder()?;
        blit.copy_from_texture_to_buffer(
            &witness,
            0,
            0,
            Origin::new(0, 0, 0),
            Size::new(SIDE, SIDE, 1),
            &readback,
            0,
            row,
            bytes,
            BlitOption::None,
        )?;
        blit.end_encoding()?;
        cb.commit()?;
        cb.wait_until_completed_for(Duration::from_secs(30))
            .map_err(|_| "render command timed out")?;
        if cb.status() != CommandBufferStatus::Completed {
            return Err(format!("render command ended {:?}: {:?}", cb.status(), cb.error()).into());
        }
        let host = readback.contents().ok_or("readback is not mapped")?;
        // SAFETY: The buffer is shared and the command buffer has completed.
        let host = unsafe { std::slice::from_raw_parts(host.as_ptr(), bytes as usize) };
        for (i, texel) in host.chunks_exact(16).enumerate() {
            let observed = f32::from_le_bytes(texel[..4].try_into()?);
            if observed.to_bits() != expected.to_bits() {
                return Err(format!("{load:?} pixel {i}: {observed} expected {expected}").into());
            }
        }
        println!("{load:?}: {} readback pixels match {expected}", SIDE * SIDE);
    }
    Ok(())
}
