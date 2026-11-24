//! Exercises the public render encoder with a real XR fetch and a readback attachment.
use std::error::Error;
use std::time::Duration;

use metal2vulkan::device::ApiVersion;
use metal2vulkan::metal::{BlendFactor, ColorWriteMask, PixelFormat, PrimitiveType, TextureUsage};
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

    let xr_format = PixelFormat::RGB10A82PXR10;
    let witness_format = PixelFormat::RG32Float;
    let mut pipeline =
        RenderPipelineDescriptor::new(StageSource::Function(vertex.function_descriptor()));
    pipeline.fragment = Some(StageSource::Function(fragment.function_descriptor()));
    pipeline.color_attachments[0] = Some(ColorAttachmentDescriptor::new(xr_format));
    pipeline.color_attachments[1] = Some(ColorAttachmentDescriptor::new(witness_format));
    let pipeline = device.new_render_pipeline_state(&pipeline, &PipelineOptions::default())?;
    let mut blend =
        RenderPipelineDescriptor::new(StageSource::Function(vertex.function_descriptor()));
    let blend_fragment = library.new_function_with_name("xr_blend")?;
    blend.fragment = Some(StageSource::Function(blend_fragment.function_descriptor()));
    let mut xr_blend = ColorAttachmentDescriptor::new(xr_format);
    xr_blend.blending_enabled = true;
    xr_blend.destination_rgb_blend_factor = BlendFactor::One;
    blend.color_attachments[1] = Some(ColorAttachmentDescriptor::new(witness_format));
    let mut blended = |mask| {
        xr_blend.write_mask = mask;
        blend.color_attachments[0] = Some(xr_blend);
        device.new_render_pipeline_state(&blend, &PipelineOptions::default())
    };
    let all = blended(ColorWriteMask::ALL)?;
    let red = blended(ColorWriteMask::RED | ColorWriteMask::BLUE)?;

    let texture = |format| {
        let mut descriptor = TextureDescriptor::texture_2d(format, SIDE, SIDE, false);
        descriptor.usage = TextureUsage::RENDER_TARGET;
        descriptor.resource_options = ResourceOptions::private();
        device.new_texture(&descriptor)
    };
    let xr = texture(xr_format)?;
    let witness = texture(witness_format)?;
    let queue = device.new_command_queue()?;
    let row = SIDE * 8;
    let bytes = row * SIDE;
    let readback = device.new_buffer(bytes, ResourceOptions::shared())?;

    let mut pass = RenderPassDescriptor::new();
    pass.color_attachments[0].texture = Some(xr);
    pass.color_attachments[0].store_action = StoreAction::Store;
    pass.color_attachments[0].clear_color = ClearColor::new(0.5, 0.125, -0.125, 1.0);
    pass.color_attachments[1].texture = Some(witness.clone());
    pass.color_attachments[1].load_action = LoadAction::Clear;
    pass.color_attachments[1].store_action = StoreAction::Store;

    for (load, draws, blend, expected, green) in [
        (LoadAction::Clear, 3, None, 0.5009765625_f32, None),
        (LoadAction::Load, 1, None, 0.501953125_f32, None),
        (LoadAction::Clear, 1, Some(&all), 0.625_f32, Some(0.375_f32)),
        (LoadAction::Clear, 1, Some(&red), 0.625_f32, Some(0.125_f32)),
    ] {
        pass.color_attachments[0].load_action = load;
        let cb = queue.command_buffer()?;
        let mut render = cb.render_command_encoder(&pass)?;
        if let Some(blend) = blend {
            render.set_render_pipeline_state(blend)?;
            render.draw_primitives(PrimitiveType::Triangle, 0, 3, 1, 0)?;
        }
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
        for (i, texel) in host.chunks_exact(8).enumerate() {
            let observed = f32::from_le_bytes(texel[..4].try_into()?);
            if observed.to_bits() != expected.to_bits() {
                return Err(format!("{load:?} pixel {i}: {observed} expected {expected}").into());
            }
            if let Some(green) = green {
                let observed = f32::from_le_bytes(texel[4..8].try_into()?);
                if observed.to_bits() != green.to_bits() {
                    return Err(format!("green at pixel {i}: {observed} expected {green}").into());
                }
            }
        }
        println!(
            "{load:?}, green={green:?}: {} readback pixels match {expected}",
            SIDE * SIDE
        );
    }
    let make = |vertex: &str, fragment: &str| {
        let mut descriptor = RenderPipelineDescriptor::new(StageSource::Function(
            library
                .new_function_with_name(vertex)?
                .function_descriptor(),
        ));
        descriptor.fragment = Some(StageSource::Function(
            library
                .new_function_with_name(fragment)?
                .function_descriptor(),
        ));
        descriptor.color_attachments[0] = Some(ColorAttachmentDescriptor::new(xr_format));
        descriptor.color_attachments[1] = Some(ColorAttachmentDescriptor::new(witness_format));
        device.new_render_pipeline_state(&descriptor, &PipelineOptions::default())
    };
    let gradient = make("xr_vertex", "xr_gradient")?;
    let derivatives = make("xr_partial_vertex", "xr_derivatives")?;
    pass.color_attachments[0].load_action = LoadAction::Clear;
    pass.color_attachments[0].clear_color = ClearColor::new(0.0, 0.0, 0.0, 0.25);
    for seeded in [false, true] {
        let cb = queue.command_buffer()?;
        let mut render = cb.render_command_encoder(&pass)?;
        if seeded {
            render.set_render_pipeline_state(&gradient)?;
            render.draw_primitives(PrimitiveType::Triangle, 0, 3, 1, 0)?;
        }
        render.set_render_pipeline_state(&derivatives)?;
        render.draw_primitives(PrimitiveType::Triangle, 0, 6, 1, 0)?;
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
            .map_err(|_| "XR snapshot command timed out")?;
        if cb.status() != CommandBufferStatus::Completed {
            return Err(format!("XR snapshot ended {:?}: {:?}", cb.status(), cb.error()).into());
        }
        let host = readback.contents().ok_or("readback is not mapped")?;
        // SAFETY: The buffer is shared and the command buffer has completed.
        let host = unsafe { std::slice::from_raw_parts(host.as_ptr(), bytes as usize) };
        for (i, texel) in host.chunks_exact(8).enumerate() {
            let x = i % SIDE as usize;
            let y = i / SIDE as usize;
            let actual = (
                f32::from_le_bytes(texel[..4].try_into()?),
                f32::from_le_bytes(texel[4..8].try_into()?),
            );
            let first_dx = if seeded { 1.0 / 64.0 } else { 0.0 };
            let initial = if seeded {
                0.25 + x as f32 / 64.0 + y as f32 / 32.0
            } else {
                0.25
            };
            let expected = if x < 5 {
                (first_dx - if x == 4 { 0.125 } else { 0.0 }, initial + 0.125)
            } else {
                (0.0, 0.0)
            };
            if actual != expected {
                return Err(format!("XR snapshot seeded={seeded} pixel ({x}, {y}): {actual:?} expected {expected:?}").into());
            }
        }
        println!("XR_SNAPSHOT_PASS seeded={seeded} pixels={}", SIDE * SIDE);
    }
    Ok(())
}
