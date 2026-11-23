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

!air.vertex = !{!0}
!air.fragment = !{!5}
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
