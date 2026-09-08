"""Viewport pointer movement, drag, and coordinate click tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from ..browser.motion import Point, PointerProfile
from ..browser.targeting import ElementTarget
from ..response_errors import ErrorCode
from ..tool_outputs import (
    PageClickXYData,
    PagePointerDragData,
    PagePointerDragElementData,
    PagePointerMoveData,
)
from .base import TabScopedInput, ToolOutcome, ToolType, define_tool

if TYPE_CHECKING:
    from ..context import DrissionPageContext


class PointerDestinationError(ValueError):
    code = ErrorCode.PRECONDITION_FAILED
    public_message = "Resolved drag destination cannot be negative."


class PointerCoordinatesInput(TabScopedInput):
    """Shared input schema for bounded viewport pointer movement."""

    x: float = Field(..., ge=0, description="Viewport X coordinate in CSS pixels")
    y: float = Field(..., ge=0, description="Viewport Y coordinate in CSS pixels")
    element: str = Field(
        "", description="Human-readable element or interaction description"
    )
    profile: PointerProfile = Field(
        default="direct",
        description=(
            "Movement profile: direct emits one exact move; natural emits a "
            "deterministic 24-step eased cubic Bezier path with bounded 8-14ms "
            "intervals and an exact endpoint"
        ),
    )


class PointerWaypointInput(BaseModel):
    """One viewport point visited while the mouse button remains pressed."""

    model_config = ConfigDict(extra="forbid")

    x: float = Field(..., ge=0, description="Viewport X coordinate in CSS pixels")
    y: float = Field(..., ge=0, description="Viewport Y coordinate in CSS pixels")


class PointerDragInput(TabScopedInput):
    """Input schema for one failure-safe viewport drag action."""

    start_x: float = Field(..., ge=0, description="Viewport drag start X in CSS pixels")
    start_y: float = Field(..., ge=0, description="Viewport drag start Y in CSS pixels")
    end_x: float = Field(..., ge=0, description="Viewport drag end X in CSS pixels")
    end_y: float = Field(..., ge=0, description="Viewport drag end Y in CSS pixels")
    waypoints: list[PointerWaypointInput] = Field(
        default_factory=list,
        max_length=6,
        description=(
            "Optional ordered viewport points visited while the button remains pressed"
        ),
    )
    element: str = Field(
        "", description="Human-readable draggable element or interaction description"
    )
    profile: PointerProfile = Field(
        default="direct",
        description=(
            "Movement profile for the approach and every held segment: direct or "
            "deterministic bounded natural motion"
        ),
    )
    button: Literal["left", "right", "middle"] = Field(
        default="left", description="Mouse button held during the drag"
    )


class ElementTargetInput(BaseModel):
    """Selector path resolved immediately before a pointer action."""

    model_config = ConfigDict(extra="forbid")

    selector: str = Field(
        ..., min_length=1, max_length=2000, description="CSS or XPath selector"
    )
    frame_selector: str | None = Field(
        default=None,
        min_length=1,
        max_length=2000,
        description="Optional same-origin iframe CSS or XPath selector",
    )
    shadow_hosts: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Ordered CSS selectors for nested open shadow hosts; Shadow DOM target selectors must also be CSS",
    )
    anchor: Literal["center", "left", "right", "top", "bottom"] = "center"
    offset_x: float = Field(default=0, ge=-10000, le=10000)
    offset_y: float = Field(default=0, ge=-10000, le=10000)

    def to_target(self) -> ElementTarget:
        return ElementTarget.from_selectors(
            self.selector,
            frame_selector=self.frame_selector,
            shadow_hosts=tuple(self.shadow_hosts),
            anchor=self.anchor,
            offset_x=self.offset_x,
            offset_y=self.offset_y,
        )


class ElementDestinationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["element"]
    target: ElementTargetInput


class ElementSourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["element"]
    target: ElementTargetInput


class OffsetDestinationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["offset"]
    dx: float = Field(
        ...,
        ge=-10000,
        le=10000,
        validation_alias=AliasChoices("dx", "x"),
        description="Horizontal delta from the freshly resolved source point.",
    )
    dy: float = Field(
        ...,
        ge=-10000,
        le=10000,
        validation_alias=AliasChoices("dy", "y"),
        description="Vertical delta from the freshly resolved source point.",
    )


class TrackRatioDestinationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["track_ratio"]
    track: ElementTargetInput
    ratio: float = Field(..., ge=0, le=1)
    axis: Literal["x", "y"] = "x"


PointerElementDestination = Annotated[
    ElementDestinationInput | OffsetDestinationInput | TrackRatioDestinationInput,
    Field(discriminator="kind"),
]


class PointerDragElementInput(TabScopedInput):
    """Resolve an element and structured destination immediately before dragging."""

    source: ElementTargetInput | ElementSourceInput
    destination: PointerElementDestination
    profile: PointerProfile = "direct"
    button: Literal["left", "right", "middle"] = "left"


class ClickCoordinatesInput(PointerCoordinatesInput):
    """Input schema for a vision-directed viewport click."""

    button: Literal["left", "right", "middle"] = Field(
        default="left", description="Mouse button to press and release"
    )
    delay_before_press_ms: int = Field(
        default=0,
        ge=0,
        le=10000,
        description=(
            "Optional delay after pointer arrival and before mousePressed. "
            "This is timing control, not target-stability detection; moving targets "
            "require a fresh screenshot or selector-first action."
        ),
    )


@define_tool(
    name="page_pointer_move",
    title="Move Pointer to Coordinates",
    description=(
        "Move the viewport pointer to exact CSS pixel coordinates without pressing "
        "a button, using either one direct move or a bounded natural trajectory."
    ),
    input_schema=PointerCoordinatesInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=PagePointerMoveData,
    failure_message=lambda args, exc: (
        lambda e: f"Failed to move pointer to ({args.x}, {args.y}): {e}"
    )(exc),
)
async def pointer_move(
    context: DrissionPageContext, args: PointerCoordinatesInput
) -> ToolOutcome:
    """Move the pointer to viewport coordinates without pressing a button."""
    tab = context.current_tab_or_die()
    result = await tab.pointer.move_to(
        args.x,
        args.y,
        profile=args.profile,
    )
    return ToolOutcome().add_result(
        f"Successfully moved pointer to coordinates ({args.x:g}, {args.y:g})",
        x=args.x,
        y=args.y,
        element=args.element,
        url=tab.url,
        motion=result.to_dict(),
    )


@define_tool(
    name="page_pointer_drag",
    title="Drag Pointer Between Coordinates",
    description=(
        "Perform one failure-safe viewport drag through optional ordered waypoints "
        "using direct or bounded natural movement while the button remains pressed. "
        "Always releases the button."
    ),
    input_schema=PointerDragInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=PagePointerDragData,
    failure_message=lambda args, exc: (
        lambda e: f"Failed to drag from ({args.start_x}, {args.start_y}) to "
        f"({args.end_x}, {args.end_y}): {e}"
    )(exc),
)
async def pointer_drag(
    context: DrissionPageContext, args: PointerDragInput
) -> ToolOutcome:
    """Drag between viewport coordinates without exposing persistent button state."""
    tab = context.current_tab_or_die()
    result = await tab.pointer.drag_to(
        args.start_x,
        args.start_y,
        args.end_x,
        args.end_y,
        profile=args.profile,
        button=args.button,
        waypoints=tuple(Point(point.x, point.y) for point in args.waypoints),
    )
    return ToolOutcome().add_result(
        "Successfully completed pointer drag",
        start_x=args.start_x,
        start_y=args.start_y,
        end_x=args.end_x,
        end_y=args.end_y,
        element=args.element,
        url=tab.url,
        motion=result.to_dict(),
    )


@define_tool(
    name="page_pointer_drag_element",
    title="Drag Element to Structured Destination",
    description=(
        "Resolve a source element and element, offset, or track-ratio destination "
        "immediately before one failure-safe drag. Supports CSS/XPath in the top "
        "document or one same-origin iframe, plus CSS paths through nested open "
        "Shadow DOM hosts; use coordinate drag for visual-only targets."
    ),
    input_schema=PointerDragElementInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=PagePointerDragElementData,
    failure_message=lambda args, exc: f"Failed to resolve and drag element: {exc}",
)
async def pointer_drag_element(
    context: DrissionPageContext, args: PointerDragElementInput
) -> ToolOutcome:
    """Resolve selector geometry atomically and execute one held-button drag."""
    tab = context.current_tab_or_die()
    source_input = (
        args.source.target if isinstance(args.source, ElementSourceInput) else args.source
    )
    targets = {"source": source_input.to_target()}
    if isinstance(args.destination, ElementDestinationInput):
        targets["target"] = args.destination.target.to_target()
    elif isinstance(args.destination, TrackRatioDestinationInput):
        targets["track"] = args.destination.track.to_target()
    resolved = tab.targeting.resolve_many(targets)
    source = resolved["source"]
    destination_data: dict[str, object]
    drag_axis: Literal["x", "y"] | None = None
    if isinstance(args.destination, ElementDestinationInput):
        target = resolved["target"]
        end_x, end_y = target.point.x, target.point.y
        destination_data = {
            "kind": "element",
            "x": end_x,
            "y": end_y,
            "target": target.to_dict(),
        }
    elif isinstance(args.destination, OffsetDestinationInput):
        end_x = source.point.x + args.destination.dx
        end_y = source.point.y + args.destination.dy
        destination_data = {
            "kind": "offset",
            "x": end_x,
            "y": end_y,
            "offset_x": args.destination.dx,
            "offset_y": args.destination.dy,
        }
    else:
        track = resolved["track"]
        axis = args.destination.axis
        drag_axis = axis
        if axis == "x":
            travel = max(0.0, track.width - source.width)
            end_x = track.left + source.width / 2 + travel * args.destination.ratio
            end_y = track.top + track.height / 2
        else:
            travel = max(0.0, track.height - source.height)
            end_x = track.left + track.width / 2
            end_y = track.top + source.height / 2 + travel * args.destination.ratio
        destination_data = {
            "kind": "track_ratio",
            "x": end_x,
            "y": end_y,
            "track": track.to_dict(),
            "ratio": args.destination.ratio,
            "axis": axis,
        }
    if end_x < 0 or end_y < 0:
        raise PointerDestinationError("resolved drag destination cannot be negative")
    motion = await tab.pointer.drag_to(
        source.point.x,
        source.point.y,
        end_x,
        end_y,
        profile=args.profile,
        button=args.button,
        axis=drag_axis,
    )
    return ToolOutcome().add_result(
        "Successfully resolved and dragged element",
        source=source.to_dict(),
        destination=destination_data,
        url=tab.url,
        motion=motion.to_dict(),
    )


@define_tool(
    name="page_click_xy",
    title="Click Coordinates",
    description=(
        "Move the viewport pointer to exact CSS pixel coordinates using a direct or "
        "bounded natural trajectory, optionally wait for an explicit delay, then "
        "press and release one mouse button."
    ),
    input_schema=ClickCoordinatesInput,
    tool_type=ToolType.DESTRUCTIVE,
    output_model=PageClickXYData,
    failure_message=lambda args, exc: (
        lambda e: f"Failed to click at ({args.x}, {args.y}): {e}"
    )(exc),
)
async def click_coordinates(
    context: DrissionPageContext, args: ClickCoordinatesInput
) -> ToolOutcome:
    """Click at coordinates."""
    tab = context.current_tab_or_die()
    result = await tab.pointer.click_at(
        args.x,
        args.y,
        profile=args.profile,
        button=args.button,
        delay_before_press_ms=args.delay_before_press_ms,
    )
    return ToolOutcome().add_result(
        f"Successfully clicked at coordinates ({args.x:g}, {args.y:g})",
        x=args.x,
        y=args.y,
        element=args.element,
        url=tab.url,
        motion=result.to_dict(),
    )
