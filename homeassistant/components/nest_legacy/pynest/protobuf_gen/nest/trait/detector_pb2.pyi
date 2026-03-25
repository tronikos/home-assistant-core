import datetime

from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class OpenCloseTrait(_message.Message):
    __slots__ = ("openCloseState", "firstObservedAt", "firstObservedAtMs")
    class OpenCloseState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        OPEN_CLOSE_STATE_UNSPECIFIED: _ClassVar[OpenCloseTrait.OpenCloseState]
        OPEN_CLOSE_STATE_CLOSED: _ClassVar[OpenCloseTrait.OpenCloseState]
        OPEN_CLOSE_STATE_OPEN: _ClassVar[OpenCloseTrait.OpenCloseState]
        OPEN_CLOSE_STATE_UNKNOWN: _ClassVar[OpenCloseTrait.OpenCloseState]
        OPEN_CLOSE_STATE_INVALID_CALIBRATION: _ClassVar[OpenCloseTrait.OpenCloseState]
    OPEN_CLOSE_STATE_UNSPECIFIED: OpenCloseTrait.OpenCloseState
    OPEN_CLOSE_STATE_CLOSED: OpenCloseTrait.OpenCloseState
    OPEN_CLOSE_STATE_OPEN: OpenCloseTrait.OpenCloseState
    OPEN_CLOSE_STATE_UNKNOWN: OpenCloseTrait.OpenCloseState
    OPEN_CLOSE_STATE_INVALID_CALIBRATION: OpenCloseTrait.OpenCloseState
    class OpenCloseEvent(_message.Message):
        __slots__ = ("openCloseState", "priorOpenCloseState")
        OPENCLOSESTATE_FIELD_NUMBER: _ClassVar[int]
        PRIOROPENCLOSESTATE_FIELD_NUMBER: _ClassVar[int]
        openCloseState: OpenCloseTrait.OpenCloseState
        priorOpenCloseState: OpenCloseTrait.OpenCloseState
        def __init__(self, openCloseState: _Optional[_Union[OpenCloseTrait.OpenCloseState, str]] = ..., priorOpenCloseState: _Optional[_Union[OpenCloseTrait.OpenCloseState, str]] = ...) -> None: ...
    OPENCLOSESTATE_FIELD_NUMBER: _ClassVar[int]
    FIRSTOBSERVEDAT_FIELD_NUMBER: _ClassVar[int]
    FIRSTOBSERVEDATMS_FIELD_NUMBER: _ClassVar[int]
    openCloseState: OpenCloseTrait.OpenCloseState
    firstObservedAt: _timestamp_pb2.Timestamp
    firstObservedAtMs: _timestamp_pb2.Timestamp
    def __init__(self, openCloseState: _Optional[_Union[OpenCloseTrait.OpenCloseState, str]] = ..., firstObservedAt: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., firstObservedAtMs: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class AmbientMotionTrait(_message.Message):
    __slots__ = ()
    class AmbientMotionEvent(_message.Message):
        __slots__ = ("startMotion", "maxHoldOff")
        STARTMOTION_FIELD_NUMBER: _ClassVar[int]
        MAXHOLDOFF_FIELD_NUMBER: _ClassVar[int]
        startMotion: _timestamp_pb2.Timestamp
        maxHoldOff: _duration_pb2.Duration
        def __init__(self, startMotion: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., maxHoldOff: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class AmbientMotionSettingsTrait(_message.Message):
    __slots__ = ("enableDetection",)
    ENABLEDETECTION_FIELD_NUMBER: _ClassVar[int]
    enableDetection: bool
    def __init__(self, enableDetection: bool = ...) -> None: ...

class AmbientMotionTimingSettingsTrait(_message.Message):
    __slots__ = ("maxHoldOff", "overrideMaxHoldOff")
    MAXHOLDOFF_FIELD_NUMBER: _ClassVar[int]
    OVERRIDEMAXHOLDOFF_FIELD_NUMBER: _ClassVar[int]
    maxHoldOff: _duration_pb2.Duration
    overrideMaxHoldOff: bool
    def __init__(self, maxHoldOff: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., overrideMaxHoldOff: bool = ...) -> None: ...
