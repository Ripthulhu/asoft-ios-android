; Authored AIR fixture for the XR render-pass boundary test.
source_filename = "xr_tile_draw"
target datalayout = "e-p:64:64:64-i1:8:8-i8:8-i16:16:16-i32:32:32-i64:64:64-f32:32:32-f64:64:64-v16:16:16-v24:32:32-v32:32:32-v48:64:64-v64:64:64-v96:128:128-v128:128:128-v192:256:256-v256:256:256-v512:512:512-v1024:1024:1024-n8:16:32"
target triple = "air64_v28-apple-macosx26.0.0"

define <4 x float> @xr_vertex(i32 %id) {
  %right = icmp eq i32 %id, 1
  %top = icmp eq i32 %id, 2
  %x = select i1 %right, float 3.0, float -1.0
  %y = select i1 %top, float 3.0, float -1.0
  %v = insertelement <4 x float> <float 0.0, float 0.0, float 0.0, float 1.0>, float %x, i32 0
  %out = insertelement <4 x float> %v, float %y, i32 1
  ret <4 x float> %out
}

define <{ <4 x float>, <4 x float> }> @xr_fragment(<4 x float> %tile) {
  %advanced = fadd <4 x float> %tile, <float 0.00048828125, float 0.0, float 0.0, float 0.0>
  %xr = insertvalue <{ <4 x float>, <4 x float> }> poison, <4 x float> %advanced, 0
  %out = insertvalue <{ <4 x float>, <4 x float> }> %xr, <4 x float> %tile, 1
  ret <{ <4 x float>, <4 x float> }> %out
}

define <4 x float> @xr_partial_vertex(i32 %id) {
  %lane = urem i32 %id, 3
  %left = icmp eq i32 %lane, 2
  %bottom = icmp eq i32 %lane, 1
  %x = select i1 %left, float -3.0, float -0.375
  %y = select i1 %bottom, float -3.0, float 1.0
  %v = insertelement <4 x float> <float 0.0, float 0.0, float 0.25, float 1.0>, float %x, i32 0
  %out = insertelement <4 x float> %v, float %y, i32 1
  ret <4 x float> %out
}

define <{ <4 x float>, <2 x float> }> @xr_gradient(<4 x float> %tile, <4 x float> %position) {
  %px = extractelement <4 x float> %position, i32 0
  %py = extractelement <4 x float> %position, i32 1
  %x = fsub float %px, 0.5
  %y = fsub float %py, 0.5
  %col = fmul float %x, 0.015625
  %row = fmul float %y, 0.03125
  %gradient = fadd float %col, %row
  %clear = extractelement <4 x float> %tile, i32 3
  %alpha = fadd float %clear, %gradient
  %color = insertelement <4 x float> %tile, float %alpha, i32 3
  %out = insertvalue <{ <4 x float>, <2 x float> }> poison, <4 x float> %color, 0
  %result = insertvalue <{ <4 x float>, <2 x float> }> %out, <2 x float> zeroinitializer, 1
  ret <{ <4 x float>, <2 x float> }> %result
}

define <{ <4 x float>, <2 x float> }> @xr_derivatives(<4 x float> %tile) {
  %alpha = extractelement <4 x float> %tile, i32 3
  %dx = call float @air.dfdx.f32(float %alpha)
  %w0 = insertelement <2 x float> poison, float %dx, i32 0
  %witness = insertelement <2 x float> %w0, float %alpha, i32 1
  %next = fadd float %alpha, 0.125
  %color = insertelement <4 x float> %tile, float %next, i32 3
  %out = insertvalue <{ <4 x float>, <2 x float> }> poison, <4 x float> %color, 0
  %result = insertvalue <{ <4 x float>, <2 x float> }> %out, <2 x float> %witness, 1
  ret <{ <4 x float>, <2 x float> }> %result
}

declare float @air.dfdx.f32(float)

!air.vertex = !{!0, !18}
define <{ <4 x half>, <2 x half> }> @xr_blend() {
  ret <{ <4 x half>, <2 x half> }> <{ <4 x half> <half 0xH3000, half 0xH3400, half 0xH0000, half 0xH0000>, <2 x half> zeroinitializer }>
}

!air.fragment = !{!5, !13, !19, !20}
!air.version = !{!11}
!air.language_version = !{!12}
!0 = !{ptr @xr_vertex, !1, !3}
!1 = !{!2}
!2 = !{!"air.position", !"air.arg_type_name", !"float4"}
!3 = !{!4}
!4 = !{i32 0, !"air.vertex_id", !"air.arg_type_name", !"uint", !"air.arg_name", !"id"}
!5 = !{ptr @xr_fragment, !6, !9}
!6 = !{!7, !8}
!7 = !{!"air.render_target", i32 0, i32 0, !"air.arg_type_name", !"float4", !"air.arg_name", !"xr"}
!8 = !{!"air.render_target", i32 1, i32 0, !"air.arg_type_name", !"float4", !"air.arg_name", !"witness"}
!9 = !{!10}
!10 = !{i32 0, !"air.render_target", i32 0, !"air.arg_type_name", !"float4", !"air.arg_name", !"tile"}
!11 = !{i32 2, i32 8, i32 0}
!12 = !{!"Metal", i32 4, i32 0, i32 0}
!13 = !{ptr @xr_blend, !14, !16}
!14 = !{!15, !17}
!15 = !{!"air.render_target", i32 0, i32 0, !"air.arg_type_name", !"half4", !"air.arg_name", !"color"}
!16 = !{}
!17 = !{!"air.render_target", i32 1, i32 0, !"air.arg_type_name", !"half2", !"air.arg_name", !"coverage"}
!18 = !{ptr @xr_partial_vertex, !1, !3}
!19 = !{ptr @xr_gradient, !21, !22}
!20 = !{ptr @xr_derivatives, !21, !9}
!21 = !{!7, !23}
!22 = !{!10, !24}
!23 = !{!"air.render_target", i32 1, i32 0, !"air.arg_type_name", !"float2", !"air.arg_name", !"witness"}
!24 = !{i32 1, !"air.position", !"air.center", !"air.no_perspective", !"air.arg_type_name", !"float4", !"air.arg_name", !"position"}
