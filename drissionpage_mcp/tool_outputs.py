"""Typed data models returned by public MCP tools."""

from __future__ import annotations

import re
from datetime import datetime
from ipaddress import ip_address
from pathlib import PurePosixPath
from typing import Annotated, Any, Literal, cast
from urllib.parse import urlsplit, urlunsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    StringConstraints,
    field_validator,
    model_validator,
)


class ToolData(BaseModel):
    """Strict base for tool data payloads."""

    model_config = ConfigDict(extra="forbid")


class TabScopedData(ToolData):
    """Success payload base for operations bound to one browser tab.

    The field is optional for direct handler/unit-test calls and is populated by
    the server after it captures the target tab.  Keeping it on a dedicated base
    avoids adding target metadata to browser-wide or context-only responses.
    """

    tab_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="MCP tab id captured for this operation.",
    )


class ContractData(BaseModel):
    """Strict immutable base for shared task-runtime contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


ContractId = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9_-]{2,127}$"),
]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
SafeRelativePath = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=500,
        pattern=r"^[^/\\:]+(?:/[^/\\:]+)*$",
    ),
]
PublicSourceUrl = Annotated[
    str,
    StringConstraints(
        max_length=500,
        pattern=r"^(?:|https?://[^/?#\s]+(?:/[^?#\s\\]*)?)$",
    ),
]

_HOST_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.I)
_INVALID_PERCENT_ESCAPE_RE = re.compile(r"%(?![0-9a-f]{2})", re.I)


def _normalize_public_host(hostname: str) -> str:
    """Return one normalized domain/IP literal or an empty invalid marker."""

    try:
        address = ip_address(hostname)
    except ValueError:
        try:
            ascii_host = hostname.encode("idna").decode("ascii").rstrip(".")
        except UnicodeError:
            return ""
        if len(ascii_host) > 253 or not all(
            _HOST_LABEL_RE.fullmatch(label) for label in ascii_host.split(".")
        ):
            return ""
        return ascii_host.lower()
    return f"[{address.compressed}]" if address.version == 6 else address.compressed


def sanitize_public_url(value: Any) -> str:
    """Return a query-free public HTTP(S) URL or an empty redaction."""

    if not isinstance(value, str) or not value:
        return ""
    if "\\" in value or any(
        character.isspace() or ord(character) < 32 for character in value
    ):
        return ""
    try:
        parts = urlsplit(value)
        hostname = parts.hostname
        port = parts.port
    except (TypeError, ValueError):
        return ""
    if (
        parts.scheme.lower() not in {"http", "https"}
        or not hostname
        or not hostname.strip(".")
        or (parts.path and not parts.path.startswith("/"))
        or _INVALID_PERCENT_ESCAPE_RE.search(parts.path)
    ):
        return ""
    normalized_host = _normalize_public_host(hostname)
    if not normalized_host:
        return ""
    netloc = normalized_host if port is None else f"{normalized_host}:{port}"
    sanitized = urlunsplit((parts.scheme.lower(), netloc, parts.path, "", ""))
    return sanitized if len(sanitized) <= 500 else ""


class ActionReceipt(ContractData):
    """Redacted evidence for one live-task consequential browser invocation."""

    schema_version: Literal["1"] = "1"
    action_id: ContractId
    task_id: ContractId
    operation_key: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    request_fingerprint: Sha256Hex
    kind: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    side_effect: Literal["external_download", "dialog_response", "artifact_write"]
    status: Literal[
        "success",
        "validation_failed",
        "indeterminate",
        "failed",
    ]
    started_at: datetime
    finished_at: datetime
    tab_id: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    target_fingerprint: Sha256Hex | None = None
    artifact_ids: Annotated[tuple[ContractId, ...], Field(max_length=16)] = Field(
        default_factory=tuple
    )
    error_code: (
        Annotated[str, StringConstraints(min_length=1, max_length=100)] | None
    ) = None
    redacted: Literal[True] = True

    @model_validator(mode="after")
    def validate_timestamps(self) -> ActionReceipt:
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must not precede started_at")
        return self


class ArtifactRef(ContractData):
    """Safe metadata for one complete artifact produced in the live task."""

    schema_version: Literal["1"] = "1"
    artifact_id: ContractId
    task_id: ContractId
    producing_action_id: ContractId
    kind: Literal["download", "page_export"]
    filename: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    mime_type: (
        Annotated[str, StringConstraints(min_length=1, max_length=200)] | None
    ) = None
    size_bytes: Annotated[int, Field(ge=0)]
    sha256: Sha256Hex
    safe_relative_path: SafeRelativePath
    source_url: PublicSourceUrl = ""
    created_at: datetime
    status: Literal["complete"] = "complete"
    redacted: bool = False

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        if value in {".", ".."} or PurePosixPath(value).name != value:
            raise ValueError("filename must be a basename")
        return value

    @field_validator("safe_relative_path")
    @classmethod
    def validate_safe_relative_path(cls, value: str) -> str:
        if "\\" in value or ":" in value.split("/", 1)[0]:
            raise ValueError("safe_relative_path must use relative POSIX syntax")
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "." in path.parts:
            raise ValueError("safe_relative_path must be a normalized relative path")
        return path.as_posix()

    @field_validator("source_url", mode="before")
    @classmethod
    def sanitize_source_url(cls, value: Any) -> str:
        return sanitize_public_url(value)


class CapabilityProbe(ContractData):
    """Evidence-backed state for one browser/runtime capability."""

    name: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_.-]{1,63}$")]
    status: Literal["unprobed", "supported", "unsupported", "degraded"]
    evidence_source: Literal[
        "none",
        "runtime_probe",
        "browser_event",
        "integration_probe",
    ] = "none"
    reason_code: (
        Annotated[str, StringConstraints(min_length=1, max_length=100)] | None
    ) = None
    checked_at: datetime | None = None

    @model_validator(mode="after")
    def validate_probe_evidence(self) -> CapabilityProbe:
        if self.status == "unprobed":
            if self.evidence_source != "none" or self.checked_at is not None:
                raise ValueError("unprobed capabilities cannot include probe evidence")
        elif self.evidence_source == "none" or self.checked_at is None:
            raise ValueError(
                "probed capabilities require evidence_source and checked_at"
            )
        if self.status == "supported" and self.evidence_source not in {
            "browser_event",
            "integration_probe",
        }:
            raise ValueError("supported capabilities require behavioral probe evidence")
        return self


class CapabilitySet(ContractData):
    """Bounded capability discovery snapshot without implicit probing."""

    schema_version: Literal["1"] = "1"
    overall_status: Literal["unprobed", "supported", "unsupported", "degraded"] = (
        "unprobed"
    )
    drissionpage_version: Annotated[str, StringConstraints(max_length=100)] = ""
    browser_product: Annotated[str, StringConstraints(max_length=100)] = ""
    browser_version: Annotated[str, StringConstraints(max_length=100)] = ""
    capabilities: Annotated[tuple[CapabilityProbe, ...], Field(max_length=24)] = Field(
        default_factory=tuple
    )


class PageNavigateData(TabScopedData):
    url: str
    final_url: str
    new_tab: bool
    background: bool = False
    new_window: bool = False
    new_context: bool = False
    active: bool = True
    tab_id: str
    changes: dict[str, Any] | None = None


class PageNavigateWithHttpAuthData(ToolData):
    url: str
    final_url: str
    authenticated: bool
    tab_id: str
    realm: str | None = None
    challenge_count: int | None = None
    response_status: int | None = None
    handlers_cleaned: bool | None = None
    credential_scope: Literal["isolated_browser_context"] | None = None
    username_provided: bool | None = None
    password_provided: bool | None = None
    credentials_redacted: Literal[True] | None = None


class PageGoBackData(TabScopedData):
    url: str


class PageGoForwardData(TabScopedData):
    url: str


class PageRefreshData(TabScopedData):
    url: str


class TabListData(ToolData):
    tabs: list[dict[str, Any]]
    count: int
    active_tab_id: str


class TabSwitchData(ToolData):
    tab: dict[str, Any]
    tab_id: str
    url: str


class TabCloseData(ToolData):
    closed: Literal[True]
    tab_id: str
    remaining_count: int
    active_tab_id: str


class PageResizeData(TabScopedData):
    width: int
    height: int


class PageScreenshotData(TabScopedData):
    screenshot: dict[str, Any]


class PageScreenshotSaveData(TabScopedData):
    screenshot: dict[str, Any]


class PageExportArtifactReceipt(ActionReceipt):
    kind: Literal["page_export_artifact"]
    side_effect: Literal["artifact_write"]
    status: Literal["success"]
    artifact_ids: Annotated[tuple[ContractId, ...], Field(min_length=1, max_length=1)]


class PageExportArtifactData(TabScopedData):
    operation_key: str
    format: Literal["pdf", "mhtml"]
    artifact: ArtifactRef
    receipt: PageExportArtifactReceipt

    @model_validator(mode="after")
    def validate_correlations(self) -> PageExportArtifactData:
        if self.receipt.operation_key != self.operation_key:
            raise ValueError("receipt operation_key must match data operation_key")
        if self.artifact.kind != "page_export":
            raise ValueError("page export artifact must use page_export kind")
        if self.artifact.task_id != self.receipt.task_id:
            raise ValueError("artifact task_id must match receipt task_id")
        if self.artifact.producing_action_id != self.receipt.action_id:
            raise ValueError(
                "artifact producing_action_id must match receipt action_id"
            )
        if self.receipt.artifact_ids != (self.artifact.artifact_id,):
            raise ValueError("receipt artifact_ids must contain the artifact id")
        return self


class PageSnapshotData(TabScopedData):
    url: str
    title: str
    text_excerpt: str
    headings: list[dict[str, Any]]
    links: list[dict[str, Any]]
    buttons: list[dict[str, Any]]
    inputs: list[dict[str, Any]]
    forms: list[dict[str, Any]]
    counts: dict[str, int]
    truncated: dict[str, Any]
    limits: dict[str, Any]
    meta: dict[str, Any]


class PageObservation(TabScopedData):
    url: str
    title: str
    ready_state: str
    counts: dict[str, int]
    text_samples: list[str]
    active_element: Any
    console: dict[str, Any]
    limits: dict[str, Any]


class PageEvaluateData(TabScopedData):
    result: Any
    result_type: str
    non_finite_number: Literal["Infinity", "-Infinity", "NaN"] | None = None
    truncated: bool
    original_json_chars: int
    max_chars: int


class PointerMoveData(ToolData):
    profile: Literal["direct", "natural"]
    start_x: float
    start_y: float
    target_x: float
    target_y: float
    steps: int
    planned_duration_ms: int


class PointerMotionData(PointerMoveData):
    button: Literal["left", "right", "middle"]
    delay_before_press_ms: int


class PagePointerMoveData(TabScopedData):
    x: float
    y: float
    element: str
    url: str
    motion: PointerMoveData


class PointerDragData(ToolData):
    profile: Literal["direct", "natural"]
    button: Literal["left", "right", "middle"]
    start_x: float
    start_y: float
    target_x: float
    target_y: float
    approach_steps: int
    drag_steps: int
    waypoint_count: int
    planned_duration_ms: int


class PagePointerDragData(TabScopedData):
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    element: str
    url: str
    motion: PointerDragData


class ResolvedPointerTargetData(ToolData):
    selector: str
    locator: str
    selector_strategy: str
    selector_normalized: bool
    frame_selector: str | None
    shadow_hosts: list[str]
    anchor: Literal["center", "left", "right", "top", "bottom"]
    offset_x: float
    offset_y: float
    x: float
    y: float
    left: float
    top: float
    right: float
    bottom: float
    width: float
    height: float


class PointerDragElementDestinationData(ToolData):
    kind: Literal["element", "offset", "track_ratio"]
    x: float
    y: float
    target: ResolvedPointerTargetData | None = None
    track: ResolvedPointerTargetData | None = None
    offset_x: float | None = None
    offset_y: float | None = None
    ratio: float | None = None
    axis: Literal["x", "y"] | None = None


class PagePointerDragElementData(TabScopedData):
    source: ResolvedPointerTargetData
    destination: PointerDragElementDestinationData
    url: str
    motion: PointerDragData


class PageClickXYData(TabScopedData):
    x: float
    y: float
    element: str
    url: str
    motion: PointerMotionData


class PageCloseData(ToolData):
    closed: Literal[True]


class PageGetUrlData(TabScopedData):
    url: str


class BrowserHeadersSetData(TabScopedData):
    count: int
    headers: dict[str, str]
    set: Literal[True]


class BrowserUserAgentSetData(TabScopedData):
    previous_user_agent: str
    user_agent: str
    platform: str | None
    set: Literal[True]


class BrowserCacheClearData(TabScopedData):
    cleared: Literal[True]


class BrowserPermissionGetData(TabScopedData):
    permission: str
    state: Literal["granted", "denied", "prompt", "unsupported"]
    origin: str
    query_supported: bool


class BrowserPermissionSetData(TabScopedData):
    permission: str
    setting: Literal["granted", "denied", "prompt"]
    origin: str
    applied: Literal[True]
    verified: bool
    observed_state: Literal["granted", "denied", "prompt", "unsupported"] | None
    context_scope: Literal["current_browser_context"]


class BrowserPermissionsResetData(TabScopedData):
    reset: Literal[True]
    context_scope: Literal["current_browser_context"]


class ConsoleLogsData(TabScopedData):
    available: bool
    listening: bool
    count: int
    total: int
    next_cursor: int
    logs: list[dict[str, Any]]


class ElementTargetData(TabScopedData):
    selector: str
    locator: str
    selector_strategy: str
    selector_normalized: bool
    target_kind: Literal["selector", "accessibility"] = "selector"
    frame_selectors: list[str] = Field(default_factory=list)
    shadow_hosts: list[str] = Field(default_factory=list)
    role: str | None = None
    name: str | None = None
    exact: bool | None = None


class ElementFindData(TabScopedData):
    element: dict[str, Any]


class ElementFindAllData(ElementTargetData):
    count: int
    returned: int
    limit: int
    truncated: bool
    elements: list[dict[str, Any]]
    meta: dict[str, Any]


class ElementClickData(ElementTargetData):
    url: str
    button: Literal["left", "right", "middle"]
    click_count: Literal[1, 2]
    changes: dict[str, Any] | None = None


class ElementClickAndDownloadSuccessReceipt(ActionReceipt):
    kind: Literal["element_click_and_download"]
    side_effect: Literal["external_download"]
    status: Literal["success"]
    artifact_ids: Annotated[tuple[ContractId, ...], Field(min_length=1, max_length=1)]


class ElementClickAndDownloadFailedReceipt(ActionReceipt):
    kind: Literal["element_click_and_download"]
    side_effect: Literal["external_download"]
    status: Literal["failed"]
    artifact_ids: Annotated[tuple[ContractId, ...], Field(max_length=0)] = ()


class ElementClickAndDownloadValidationFailedReceipt(ActionReceipt):
    kind: Literal["element_click_and_download"]
    side_effect: Literal["external_download"]
    status: Literal["validation_failed"]
    artifact_ids: Annotated[tuple[ContractId, ...], Field(max_length=0)] = ()


class ElementClickAndDownloadIndeterminateReceipt(ActionReceipt):
    kind: Literal["element_click_and_download"]
    side_effect: Literal["external_download"]
    status: Literal["indeterminate"]
    artifact_ids: Annotated[tuple[ContractId, ...], Field(max_length=0)] = ()


class CoordinateDownloadTriggerData(ToolData):
    kind: Literal["coordinate"]
    x: Annotated[float, Field(ge=0, le=100000)]
    y: Annotated[float, Field(ge=0, le=100000)]
    profile: Literal["direct", "natural"]
    delay_before_press_ms: Annotated[int, Field(ge=0, le=10000)]


class KeyboardInputMetadata(ToolData):
    provided: bool
    length: Annotated[int, Field(ge=0)]
    redacted: Literal[True]


class KeyboardDownloadTriggerData(ToolData):
    kind: Literal["keyboard"]
    keys: KeyboardInputMetadata
    interval: Annotated[float, Field(ge=0, le=2)]


DownloadTriggerData = Annotated[
    CoordinateDownloadTriggerData | KeyboardDownloadTriggerData,
    Field(discriminator="kind"),
]


class _ElementClickAndDownloadDataBase(TabScopedData):
    model_config = ConfigDict(
        json_schema_extra={
            "oneOf": [
                {
                    "required": [
                        "selector",
                        "locator",
                        "selector_strategy",
                        "selector_normalized",
                    ],
                    "properties": {
                        "selector": {"type": "string"},
                        "locator": {"type": "string"},
                        "selector_strategy": {"type": "string"},
                        "selector_normalized": {"type": "boolean"},
                    },
                    "not": {"required": ["trigger"]},
                },
                {
                    "required": ["trigger"],
                    "properties": {"trigger": {"not": {"type": "null"}}},
                    "not": {
                        "anyOf": [
                            {"required": ["selector"]},
                            {"required": ["locator"]},
                            {"required": ["selector_strategy"]},
                            {"required": ["selector_normalized"]},
                            {"required": ["target_kind"]},
                            {"required": ["frame_selectors"]},
                            {"required": ["shadow_hosts"]},
                            {"required": ["role"]},
                            {"required": ["name"]},
                            {"required": ["exact"]},
                        ]
                    },
                },
            ]
        }
    )

    operation_key: str
    selector: str | None = None
    locator: str | None = None
    selector_strategy: str | None = None
    selector_normalized: bool | None = None
    target_kind: Literal["selector", "accessibility"] | None = None
    frame_selectors: list[str] | None = None
    shadow_hosts: list[str] | None = None
    role: str | None = None
    name: str | None = None
    exact: bool | None = None
    trigger: DownloadTriggerData | None = None

    @model_validator(mode="after")
    def validate_target_shape(self) -> _ElementClickAndDownloadDataBase:
        selector_fields = (
            self.selector,
            self.locator,
            self.selector_strategy,
            self.selector_normalized,
        )
        if self.trigger is None and any(value is None for value in selector_fields):
            raise ValueError("selector download results require selector metadata")
        if self.trigger is not None and any(
            value is not None
            for value in (
                *selector_fields,
                self.target_kind,
                self.frame_selectors,
                self.shadow_hosts,
                self.role,
                self.name,
                self.exact,
            )
        ):
            raise ValueError("non-selector download results cannot include selector metadata")
        return self


class ElementClickAndDownloadSuccessData(_ElementClickAndDownloadDataBase):
    status: Literal["success"]
    artifact: ArtifactRef
    receipt: ElementClickAndDownloadSuccessReceipt

    @model_validator(mode="after")
    def validate_correlations(self) -> ElementClickAndDownloadSuccessData:
        if self.receipt.operation_key != self.operation_key:
            raise ValueError("receipt operation_key must match data operation_key")
        if self.artifact.task_id != self.receipt.task_id:
            raise ValueError("artifact task_id must match receipt task_id")
        if self.artifact.producing_action_id != self.receipt.action_id:
            raise ValueError(
                "artifact producing_action_id must match receipt action_id"
            )
        if self.receipt.artifact_ids != (self.artifact.artifact_id,):
            raise ValueError(
                "receipt artifact_ids must contain exactly the artifact id"
            )
        return self


class ElementClickAndDownloadFailedData(_ElementClickAndDownloadDataBase):
    status: Literal["failed"]
    artifact: None
    receipt: ElementClickAndDownloadFailedReceipt

    @model_validator(mode="after")
    def validate_operation_key(self) -> ElementClickAndDownloadFailedData:
        if self.receipt.operation_key != self.operation_key:
            raise ValueError("receipt operation_key must match data operation_key")
        return self


class ElementClickAndDownloadValidationFailedData(_ElementClickAndDownloadDataBase):
    status: Literal["validation_failed"]
    artifact: None
    receipt: ElementClickAndDownloadValidationFailedReceipt

    @model_validator(mode="after")
    def validate_operation_key(self) -> ElementClickAndDownloadValidationFailedData:
        if self.receipt.operation_key != self.operation_key:
            raise ValueError("receipt operation_key must match data operation_key")
        return self


class ElementClickAndDownloadIndeterminateData(_ElementClickAndDownloadDataBase):
    status: Literal["indeterminate"]
    artifact: None
    receipt: ElementClickAndDownloadIndeterminateReceipt

    @model_validator(mode="after")
    def validate_operation_key(self) -> ElementClickAndDownloadIndeterminateData:
        if self.receipt.operation_key != self.operation_key:
            raise ValueError("receipt operation_key must match data operation_key")
        return self


ElementClickAndDownloadVariant = Annotated[
    ElementClickAndDownloadSuccessData | ElementClickAndDownloadFailedData | ElementClickAndDownloadValidationFailedData | ElementClickAndDownloadIndeterminateData,
    Field(discriminator="status"),
]


class ElementClickAndDownloadData(RootModel[ElementClickAndDownloadVariant]):
    """Status-discriminated download result with correlated public evidence."""


class ElementTypeData(ElementTargetData):
    typed: Literal[True]
    cleared: bool
    changes: dict[str, Any] | None = None


class ElementGetTextData(ElementTargetData):
    text: str


class ElementGetAttributeData(ElementTargetData):
    attribute: str
    value: str | None


class ElementGetPropertyData(ElementTargetData):
    property: str
    value: Any


class ElementGetHtmlData(ElementTargetData):
    html: str


class ElementUploadFileData(ElementTargetData):
    uploaded: Literal[True]
    file_count: int
    filenames: list[str]


class ElementClickAndUploadData(ElementTargetData):
    uploaded: Literal[True]
    file_count: int
    filenames: list[str]


class PointData(ToolData):
    x: float
    y: float


class SizeData(ToolData):
    width: float
    height: float


class ElementRectData(ToolData):
    location: PointData
    size: SizeData
    midpoint: PointData
    click_point: PointData
    viewport_location: PointData
    viewport_midpoint: PointData
    viewport_click_point: PointData
    coordinate_space: Literal["target_document"]
    viewport_coordinate_space: Literal[
        "top_level_viewport", "target_document_viewport"
    ]


class ElementPresentationData(ToolData):
    display: str
    visibility: str
    opacity: float | None
    pointer_events: str
    transform: str
    transform_style: str
    perspective: str
    transformed: bool
    ancestor_3d: bool
    three_dimensional: bool
    coordinate_actionability: Literal[
        "ready",
        "hidden",
        "off_viewport",
        "covered",
        "pointer_disabled",
        "transformed_3d",
        "target_document_only",
    ]


class ElementViewportEvidenceData(ToolData):
    displayed: bool
    enabled: bool
    alive: bool
    clickable: bool
    checked: bool
    selected: bool
    in_viewport: bool
    whole_in_viewport: bool
    covered: bool
    covering_backend_node_id: int | None
    rect: ElementRectData
    presentation: ElementPresentationData


class PageScrollData(TabScopedData):
    direction: str
    pixels: int
    x: int
    y: int
    url: str


class ElementScrollIntoViewData(ElementTargetData):
    center: bool
    scroll_method: Literal["element", "page_fallback"]
    before: ElementViewportEvidenceData
    after: ElementViewportEvidenceData
    url: str


class ElementHoverData(ElementTargetData):
    url: str
    offset_x: int | None
    offset_y: int | None


class KeyboardPressData(TabScopedData):
    keys: KeyboardInputMetadata
    interval: float
    url: str


class ElementSelectData(ElementTargetData):
    selected: Literal[True]
    by: str
    value: str


class ElementCheckData(ElementTargetData):
    checked: bool
    by_js: bool


class DialogMessageMetadata(ToolData):
    present: bool
    length: Annotated[int, Field(ge=0)]
    redacted: Literal[True]


class DialogPromptMetadata(ToolData):
    provided: bool
    length: Annotated[int, Field(ge=0)]
    redacted: Literal[True]


class PageDialogRespondData(TabScopedData):
    dialog_type: Literal["alert", "confirm", "prompt"]
    action: Literal["accept", "dismiss"]
    handled: Literal[True]
    dialog_message: DialogMessageMetadata
    prompt: DialogPromptMetadata
    final_url: str
    receipt: ActionReceipt


class PageDialogObserveData(TabScopedData):
    pending: bool
    timed_out: bool
    dialog_type: Literal["alert", "confirm", "prompt"] | None
    message: str
    message_truncated: bool
    timeout: float


class FrameSummaryData(ToolData):
    index: int
    selector: str
    id: str
    name: str
    title: str
    url: str
    boundary: Literal["same_origin", "cross_origin", "unknown"]
    document_access: Literal["readable", "outer_only", "unknown"]
    outer: ElementViewportEvidenceData


class FrameListData(TabScopedData):
    count: int
    returned: int
    limit: int
    frames: list[FrameSummaryData]


class FrameSnapshotData(TabScopedData):
    frame: FrameSummaryData
    url: str
    title: str
    text_excerpt: str
    headings: list[dict[str, Any]]
    links: list[dict[str, Any]]
    buttons: list[dict[str, Any]]
    inputs: list[dict[str, Any]]
    forms: list[dict[str, Any]]
    counts: dict[str, int]
    truncated: dict[str, Any]
    limits: dict[str, Any]
    meta: dict[str, Any]


class FrameFindData(TabScopedData):
    frame: FrameSummaryData
    element: dict[str, Any]


class ShadowFindData(TabScopedData):
    host: dict[str, Any]
    element: dict[str, Any]


class ShadowFindAllData(TabScopedData):
    host: dict[str, Any]
    target: dict[str, Any]
    count: int
    returned: int
    limit: int
    truncated: bool
    elements: list[dict[str, Any]]
    meta: dict[str, Any]


class BrowserCookiesGetData(TabScopedData):
    count: int
    include_values: bool
    all_domains: bool
    cookies: list[dict[str, Any]]


class BrowserCookieWriteData(ToolData):
    name: str
    value: str
    url: str = ""
    domain: str = ""
    path: str = ""
    expires: float | None = None
    secure: bool | None = None
    http_only: bool | None = None
    same_site: Literal["None", "Lax", "Strict", "no_restriction"] | None = None
    priority: Literal["Low", "Medium", "High"] | None = None
    source_scheme: Literal["Unset", "NonSecure", "Secure"] | None = None


class BrowserCookiesSetData(TabScopedData):
    count: int
    set: Literal[True]
    cookies: list[BrowserCookieWriteData]


class BrowserCookiesDeleteData(TabScopedData):
    name: str
    url: str | None
    domain: str | None
    path: str | None
    deleted: Literal[True]


class BrowserCookiesClearData(TabScopedData):
    cleared: Literal[True]


class StorageGetData(TabScopedData):
    area: str
    key: str
    include_values: bool
    count: int
    items: dict[str, str]


class StorageSetData(TabScopedData):
    area: str
    key: str
    set: Literal[True]


class StorageClearData(TabScopedData):
    area: str
    key: str
    cleared: Literal[True]


class WaitForElementData(ElementTargetData):
    found: Literal[True]
    timeout: float


class ElementStateData(ElementTargetData):
    tag: str
    text: str
    displayed: bool
    enabled: bool
    alive: bool
    clickable: bool
    checked: bool
    selected: bool
    in_viewport: bool
    whole_in_viewport: bool
    covered: bool
    covering_backend_node_id: int | None
    rect: ElementRectData
    presentation: ElementPresentationData


class AccessibilityNodeData(ToolData):
    node_id: str
    parent_id: str | None
    backend_dom_node_id: int | None
    role: str
    name: str
    description: str
    value: str
    ignored: bool
    properties: dict[str, Any]


class PageAccessibilitySnapshotData(TabScopedData):
    nodes: list[AccessibilityNodeData]
    count: int
    returned: int
    max_nodes: int
    truncated: bool
    values_included: bool
    scope: dict[str, Any] | None
    meta: dict[str, Any]


class WaitForUrlData(TabScopedData):
    url_pattern: str
    matched: Literal[True]
    url: str
    timeout: float


class WaitTimeData(ToolData):
    waited_seconds: float


class WaitUntilData(TabScopedData):
    condition: str
    selector: str
    value: str
    name: str
    matched: Literal[True]
    timeout: float
    elapsed_ms: int
    state: dict[str, Any]


class NetworkListenStartData(TabScopedData):
    listening: bool
    filters: dict[str, Any]
    started_at: str
    cleared: bool
    listener_token: str
    state: Literal["idle", "listening", "stopped", "closed"]
    consumed_count: int = Field(ge=0)
    next_cursor: int = Field(ge=0)
    timing: dict[str, int]


class NetworkListenWaitData(TabScopedData):
    listening: bool
    timed_out: bool
    count: int
    limit: int
    packets: list[dict[str, Any]]
    meta: dict[str, Any]
    listener_token: str | None
    state: Literal["idle", "listening", "stopped", "closed"]
    consumed_count: int = Field(ge=0)
    next_cursor: int = Field(ge=0)
    timeout_ms: int = Field(ge=0)
    elapsed_ms: int = Field(ge=0)
    remaining_timeout_ms: int = Field(ge=0)


class NetworkListenStopData(TabScopedData):
    listening: bool
    was_listening: bool
    cleared: bool
    listener_token: str | None
    state: Literal["idle", "listening", "stopped", "closed"]
    consumed_count: int = Field(ge=0)
    next_cursor: int = Field(ge=0)


class NetworkBlockedUrlsSetData(TabScopedData):
    count: int
    urls: list[str]
    set: Literal[True]


def tool_outcome_schema(output_model: type[ToolData]) -> dict[str, Any]:
    """Wrap typed tool data in the stable success/failure envelope."""

    data_schema = output_model.model_json_schema()
    definitions = data_schema.pop("$defs", None)
    error_data_schema = (
        data_schema
        if cast(type[BaseModel], output_model) is ElementClickAndDownloadData
        else {"type": "object", "additionalProperties": True}
    )
    schema: dict[str, Any] = {
        "type": "object",
        "oneOf": [
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["ok", "message", "data"],
                "properties": {
                    "ok": {"const": True},
                    "message": {"type": "string"},
                    "data": data_schema,
                },
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["ok", "message", "error"],
                "properties": {
                    "ok": {"const": False},
                    "message": {"type": "string"},
                    "error": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["code", "message"],
                        "properties": {
                            "code": {"type": "string"},
                            "message": {"type": "string"},
                            "details": {"type": "object", "additionalProperties": True},
                        },
                    },
                    "data": error_data_schema,
                },
            },
        ],
    }
    if definitions:
        schema["$defs"] = definitions
    return schema
