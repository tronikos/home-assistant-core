import datetime

from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from ...nest.trait import detector_pb2 as _detector_pb2
from ...nest.trait import occupancy_pb2 as _occupancy_pb2
from ...weave import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SecurityArmTrait(_message.Message):
    __slots__ = ("armState", "securityArmSessionId", "allowanceState", "allowanceExpirationTime", "exitAllowanceDuration", "armActor", "armTime")
    class SecurityArmState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SECURITY_ARM_STATE_UNSPECIFIED: _ClassVar[SecurityArmTrait.SecurityArmState]
        SECURITY_ARM_STATE_DISARMED: _ClassVar[SecurityArmTrait.SecurityArmState]
        SECURITY_ARM_STATE_SL1: _ClassVar[SecurityArmTrait.SecurityArmState]
        SECURITY_ARM_STATE_SL2: _ClassVar[SecurityArmTrait.SecurityArmState]
    SECURITY_ARM_STATE_UNSPECIFIED: SecurityArmTrait.SecurityArmState
    SECURITY_ARM_STATE_DISARMED: SecurityArmTrait.SecurityArmState
    SECURITY_ARM_STATE_SL1: SecurityArmTrait.SecurityArmState
    SECURITY_ARM_STATE_SL2: SecurityArmTrait.SecurityArmState
    class SecurityAllowanceState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SECURITY_ALLOWANCE_STATE_UNSPECIFIED: _ClassVar[SecurityArmTrait.SecurityAllowanceState]
        SECURITY_ALLOWANCE_STATE_OFF: _ClassVar[SecurityArmTrait.SecurityAllowanceState]
        SECURITY_ALLOWANCE_STATE_TIMED_ALLOWANCE: _ClassVar[SecurityArmTrait.SecurityAllowanceState]
    SECURITY_ALLOWANCE_STATE_UNSPECIFIED: SecurityArmTrait.SecurityAllowanceState
    SECURITY_ALLOWANCE_STATE_OFF: SecurityArmTrait.SecurityAllowanceState
    SECURITY_ALLOWANCE_STATE_TIMED_ALLOWANCE: SecurityArmTrait.SecurityAllowanceState
    class StatusCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATUS_CODE_UNSPECIFIED: _ClassVar[SecurityArmTrait.StatusCode]
        STATUS_CODE_ALREADY: _ClassVar[SecurityArmTrait.StatusCode]
        STATUS_CODE_UNACKNOWLEDGED_ISSUES: _ClassVar[SecurityArmTrait.StatusCode]
        STATUS_CODE_BLOCKING_ISSUES: _ClassVar[SecurityArmTrait.StatusCode]
        STATUS_CODE_OUT_OF_SCHEDULE: _ClassVar[SecurityArmTrait.StatusCode]
        STATUS_CODE_UNAUTHORIZED_STATE_CHANGE: _ClassVar[SecurityArmTrait.StatusCode]
        STATUS_CODE_LOCATION_OUT_OF_SCOPE: _ClassVar[SecurityArmTrait.StatusCode]
    STATUS_CODE_UNSPECIFIED: SecurityArmTrait.StatusCode
    STATUS_CODE_ALREADY: SecurityArmTrait.StatusCode
    STATUS_CODE_UNACKNOWLEDGED_ISSUES: SecurityArmTrait.StatusCode
    STATUS_CODE_BLOCKING_ISSUES: SecurityArmTrait.StatusCode
    STATUS_CODE_OUT_OF_SCHEDULE: SecurityArmTrait.StatusCode
    STATUS_CODE_UNAUTHORIZED_STATE_CHANGE: SecurityArmTrait.StatusCode
    STATUS_CODE_LOCATION_OUT_OF_SCOPE: SecurityArmTrait.StatusCode
    class SecurityArmResponseType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SECURITY_ARM_RESPONSE_TYPE_UNSPECIFIED: _ClassVar[SecurityArmTrait.SecurityArmResponseType]
        SECURITY_ARM_RESPONSE_TYPE_SUCCESS: _ClassVar[SecurityArmTrait.SecurityArmResponseType]
        SECURITY_ARM_RESPONSE_TYPE_FAIL_ALREADY: _ClassVar[SecurityArmTrait.SecurityArmResponseType]
        SECURITY_ARM_RESPONSE_TYPE_FAIL_UNACKNOWLEDGED_ISSUES: _ClassVar[SecurityArmTrait.SecurityArmResponseType]
        SECURITY_ARM_RESPONSE_TYPE_FAIL_BLOCKING_ISSUES: _ClassVar[SecurityArmTrait.SecurityArmResponseType]
        SECURITY_ARM_RESPONSE_TYPE_FAIL_OUT_OF_SCHEDULE: _ClassVar[SecurityArmTrait.SecurityArmResponseType]
        SECURITY_ARM_RESPONSE_TYPE_FAIL_UNAUTHORIZED_STATE_CHANGE: _ClassVar[SecurityArmTrait.SecurityArmResponseType]
        SECURITY_ARM_RESPONSE_TYPE_FAIL_LOCATION_OUT_OF_SCOPE: _ClassVar[SecurityArmTrait.SecurityArmResponseType]
    SECURITY_ARM_RESPONSE_TYPE_UNSPECIFIED: SecurityArmTrait.SecurityArmResponseType
    SECURITY_ARM_RESPONSE_TYPE_SUCCESS: SecurityArmTrait.SecurityArmResponseType
    SECURITY_ARM_RESPONSE_TYPE_FAIL_ALREADY: SecurityArmTrait.SecurityArmResponseType
    SECURITY_ARM_RESPONSE_TYPE_FAIL_UNACKNOWLEDGED_ISSUES: SecurityArmTrait.SecurityArmResponseType
    SECURITY_ARM_RESPONSE_TYPE_FAIL_BLOCKING_ISSUES: SecurityArmTrait.SecurityArmResponseType
    SECURITY_ARM_RESPONSE_TYPE_FAIL_OUT_OF_SCHEDULE: SecurityArmTrait.SecurityArmResponseType
    SECURITY_ARM_RESPONSE_TYPE_FAIL_UNAUTHORIZED_STATE_CHANGE: SecurityArmTrait.SecurityArmResponseType
    SECURITY_ARM_RESPONSE_TYPE_FAIL_LOCATION_OUT_OF_SCOPE: SecurityArmTrait.SecurityArmResponseType
    class SecurityArmCancelResponseType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SECURITY_ARM_CANCEL_RESPONSE_TYPE_UNSPECIFIED: _ClassVar[SecurityArmTrait.SecurityArmCancelResponseType]
        SECURITY_ARM_CANCEL_RESPONSE_TYPE_SUCCESS: _ClassVar[SecurityArmTrait.SecurityArmCancelResponseType]
        SECURITY_ARM_CANCEL_RESPONSE_TYPE_FAIL_ALREADY: _ClassVar[SecurityArmTrait.SecurityArmCancelResponseType]
        SECURITY_ARM_CANCEL_RESPONSE_TYPE_TOO_LATE: _ClassVar[SecurityArmTrait.SecurityArmCancelResponseType]
        SECURITY_ARM_CANCEL_RESPONSE_TYPE_FAIL_UNAUTHORIZED_STATE_CHANGE: _ClassVar[SecurityArmTrait.SecurityArmCancelResponseType]
        SECURITY_ARM_CANCEL_RESPONSE_TYPE_FAIL_LOCATION_OUT_OF_SCOPE: _ClassVar[SecurityArmTrait.SecurityArmCancelResponseType]
    SECURITY_ARM_CANCEL_RESPONSE_TYPE_UNSPECIFIED: SecurityArmTrait.SecurityArmCancelResponseType
    SECURITY_ARM_CANCEL_RESPONSE_TYPE_SUCCESS: SecurityArmTrait.SecurityArmCancelResponseType
    SECURITY_ARM_CANCEL_RESPONSE_TYPE_FAIL_ALREADY: SecurityArmTrait.SecurityArmCancelResponseType
    SECURITY_ARM_CANCEL_RESPONSE_TYPE_TOO_LATE: SecurityArmTrait.SecurityArmCancelResponseType
    SECURITY_ARM_CANCEL_RESPONSE_TYPE_FAIL_UNAUTHORIZED_STATE_CHANGE: SecurityArmTrait.SecurityArmCancelResponseType
    SECURITY_ARM_CANCEL_RESPONSE_TYPE_FAIL_LOCATION_OUT_OF_SCOPE: SecurityArmTrait.SecurityArmCancelResponseType
    class SecurityArmStateChangeReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SECURITY_ARM_STATE_CHANGE_REASON_UNSPECIFIED: _ClassVar[SecurityArmTrait.SecurityArmStateChangeReason]
        SECURITY_ARM_STATE_CHANGE_REASON_ARM_REQUEST: _ClassVar[SecurityArmTrait.SecurityArmStateChangeReason]
        SECURITY_ARM_STATE_CHANGE_REASON_ARM_CANCELLED: _ClassVar[SecurityArmTrait.SecurityArmStateChangeReason]
    SECURITY_ARM_STATE_CHANGE_REASON_UNSPECIFIED: SecurityArmTrait.SecurityArmStateChangeReason
    SECURITY_ARM_STATE_CHANGE_REASON_ARM_REQUEST: SecurityArmTrait.SecurityArmStateChangeReason
    SECURITY_ARM_STATE_CHANGE_REASON_ARM_CANCELLED: SecurityArmTrait.SecurityArmStateChangeReason
    class SecurityArmRequest(_message.Message):
        __slots__ = ("armState", "armActor", "acknowledgedIssuesSet", "locationScope")
        ARMSTATE_FIELD_NUMBER: _ClassVar[int]
        ARMACTOR_FIELD_NUMBER: _ClassVar[int]
        ACKNOWLEDGEDISSUESSET_FIELD_NUMBER: _ClassVar[int]
        LOCATIONSCOPE_FIELD_NUMBER: _ClassVar[int]
        armState: SecurityArmTrait.SecurityArmState
        armActor: SecurityActor.SecurityActorStruct
        acknowledgedIssuesSet: _containers.RepeatedCompositeFieldContainer[SecurityDecisionFact.SecurityDecisionFactStruct]
        locationScope: _common_pb2.ResourceId
        def __init__(self, armState: _Optional[_Union[SecurityArmTrait.SecurityArmState, str]] = ..., armActor: _Optional[_Union[SecurityActor.SecurityActorStruct, _Mapping]] = ..., acknowledgedIssuesSet: _Optional[_Iterable[_Union[SecurityDecisionFact.SecurityDecisionFactStruct, _Mapping]]] = ..., locationScope: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class SecurityArmResponse(_message.Message):
        __slots__ = ("responseType",)
        RESPONSETYPE_FIELD_NUMBER: _ClassVar[int]
        responseType: SecurityArmTrait.SecurityArmResponseType
        def __init__(self, responseType: _Optional[_Union[SecurityArmTrait.SecurityArmResponseType, str]] = ...) -> None: ...
    class SecurityArmCancelRequest(_message.Message):
        __slots__ = ("armActor", "locationScope")
        ARMACTOR_FIELD_NUMBER: _ClassVar[int]
        LOCATIONSCOPE_FIELD_NUMBER: _ClassVar[int]
        armActor: SecurityActor.SecurityActorStruct
        locationScope: _common_pb2.ResourceId
        def __init__(self, armActor: _Optional[_Union[SecurityActor.SecurityActorStruct, _Mapping]] = ..., locationScope: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class SecurityArmCancelResponse(_message.Message):
        __slots__ = ("responseType",)
        RESPONSETYPE_FIELD_NUMBER: _ClassVar[int]
        responseType: SecurityArmTrait.SecurityArmCancelResponseType
        def __init__(self, responseType: _Optional[_Union[SecurityArmTrait.SecurityArmCancelResponseType, str]] = ...) -> None: ...
    class SecurityArmStateChangeEvent(_message.Message):
        __slots__ = ("armState", "priorArmState", "armActor", "securityArmSessionId", "changeReason", "allowanceState", "priorAllowanceState")
        ARMSTATE_FIELD_NUMBER: _ClassVar[int]
        PRIORARMSTATE_FIELD_NUMBER: _ClassVar[int]
        ARMACTOR_FIELD_NUMBER: _ClassVar[int]
        SECURITYARMSESSIONID_FIELD_NUMBER: _ClassVar[int]
        CHANGEREASON_FIELD_NUMBER: _ClassVar[int]
        ALLOWANCESTATE_FIELD_NUMBER: _ClassVar[int]
        PRIORALLOWANCESTATE_FIELD_NUMBER: _ClassVar[int]
        armState: SecurityArmTrait.SecurityArmState
        priorArmState: SecurityArmTrait.SecurityArmState
        armActor: SecurityActor.SecurityActorStruct
        securityArmSessionId: int
        changeReason: SecurityArmTrait.SecurityArmStateChangeReason
        allowanceState: SecurityArmTrait.SecurityAllowanceState
        priorAllowanceState: SecurityArmTrait.SecurityAllowanceState
        def __init__(self, armState: _Optional[_Union[SecurityArmTrait.SecurityArmState, str]] = ..., priorArmState: _Optional[_Union[SecurityArmTrait.SecurityArmState, str]] = ..., armActor: _Optional[_Union[SecurityActor.SecurityActorStruct, _Mapping]] = ..., securityArmSessionId: _Optional[int] = ..., changeReason: _Optional[_Union[SecurityArmTrait.SecurityArmStateChangeReason, str]] = ..., allowanceState: _Optional[_Union[SecurityArmTrait.SecurityAllowanceState, str]] = ..., priorAllowanceState: _Optional[_Union[SecurityArmTrait.SecurityAllowanceState, str]] = ...) -> None: ...
    class SecurityAllowanceStateChangeEvent(_message.Message):
        __slots__ = ("allowanceState", "priorAllowanceState", "securityArmSessionId", "duration")
        ALLOWANCESTATE_FIELD_NUMBER: _ClassVar[int]
        PRIORALLOWANCESTATE_FIELD_NUMBER: _ClassVar[int]
        SECURITYARMSESSIONID_FIELD_NUMBER: _ClassVar[int]
        DURATION_FIELD_NUMBER: _ClassVar[int]
        allowanceState: SecurityArmTrait.SecurityAllowanceState
        priorAllowanceState: SecurityArmTrait.SecurityAllowanceState
        securityArmSessionId: int
        duration: _duration_pb2.Duration
        def __init__(self, allowanceState: _Optional[_Union[SecurityArmTrait.SecurityAllowanceState, str]] = ..., priorAllowanceState: _Optional[_Union[SecurityArmTrait.SecurityAllowanceState, str]] = ..., securityArmSessionId: _Optional[int] = ..., duration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...
    ARMSTATE_FIELD_NUMBER: _ClassVar[int]
    SECURITYARMSESSIONID_FIELD_NUMBER: _ClassVar[int]
    ALLOWANCESTATE_FIELD_NUMBER: _ClassVar[int]
    ALLOWANCEEXPIRATIONTIME_FIELD_NUMBER: _ClassVar[int]
    EXITALLOWANCEDURATION_FIELD_NUMBER: _ClassVar[int]
    ARMACTOR_FIELD_NUMBER: _ClassVar[int]
    ARMTIME_FIELD_NUMBER: _ClassVar[int]
    armState: SecurityArmTrait.SecurityArmState
    securityArmSessionId: int
    allowanceState: SecurityArmTrait.SecurityAllowanceState
    allowanceExpirationTime: _timestamp_pb2.Timestamp
    exitAllowanceDuration: _duration_pb2.Duration
    armActor: SecurityActor.SecurityActorStruct
    armTime: _timestamp_pb2.Timestamp
    def __init__(self, armState: _Optional[_Union[SecurityArmTrait.SecurityArmState, str]] = ..., securityArmSessionId: _Optional[int] = ..., allowanceState: _Optional[_Union[SecurityArmTrait.SecurityAllowanceState, str]] = ..., allowanceExpirationTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., exitAllowanceDuration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., armActor: _Optional[_Union[SecurityActor.SecurityActorStruct, _Mapping]] = ..., armTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class AlarmSupervisorTrait(_message.Message):
    __slots__ = ("alarmSupervisorState", "alarmingStateTime", "alarmAcknowledegeActor")
    class AlarmSupervisorState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ALARM_SUPERVISOR_STATE_UNSPECIFIED: _ClassVar[AlarmSupervisorTrait.AlarmSupervisorState]
        ALARM_SUPERVISOR_STATE_IDLE: _ClassVar[AlarmSupervisorTrait.AlarmSupervisorState]
        ALARM_SUPERVISOR_STATE_EVALUATING: _ClassVar[AlarmSupervisorTrait.AlarmSupervisorState]
        ALARM_SUPERVISOR_STATE_SILENCED: _ClassVar[AlarmSupervisorTrait.AlarmSupervisorState]
        ALARM_SUPERVISOR_STATE_ALARMING: _ClassVar[AlarmSupervisorTrait.AlarmSupervisorState]
    ALARM_SUPERVISOR_STATE_UNSPECIFIED: AlarmSupervisorTrait.AlarmSupervisorState
    ALARM_SUPERVISOR_STATE_IDLE: AlarmSupervisorTrait.AlarmSupervisorState
    ALARM_SUPERVISOR_STATE_EVALUATING: AlarmSupervisorTrait.AlarmSupervisorState
    ALARM_SUPERVISOR_STATE_SILENCED: AlarmSupervisorTrait.AlarmSupervisorState
    ALARM_SUPERVISOR_STATE_ALARMING: AlarmSupervisorTrait.AlarmSupervisorState
    class AlarmSupervisorDecisionReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ALARM_SUPERVISOR_DECISION_REASON_UNSPECIFIED: _ClassVar[AlarmSupervisorTrait.AlarmSupervisorDecisionReason]
        ALARM_SUPERVISOR_DECISION_REASON_SMASH_AND_GRAB: _ClassVar[AlarmSupervisorTrait.AlarmSupervisorDecisionReason]
        ALARM_SUPERVISOR_DECISION_REASON_USER_SILENCING: _ClassVar[AlarmSupervisorTrait.AlarmSupervisorDecisionReason]
        ALARM_SUPERVISOR_DECISION_REASON_DEVICE_ALARMING_STATE_CHANGE: _ClassVar[AlarmSupervisorTrait.AlarmSupervisorDecisionReason]
    ALARM_SUPERVISOR_DECISION_REASON_UNSPECIFIED: AlarmSupervisorTrait.AlarmSupervisorDecisionReason
    ALARM_SUPERVISOR_DECISION_REASON_SMASH_AND_GRAB: AlarmSupervisorTrait.AlarmSupervisorDecisionReason
    ALARM_SUPERVISOR_DECISION_REASON_USER_SILENCING: AlarmSupervisorTrait.AlarmSupervisorDecisionReason
    ALARM_SUPERVISOR_DECISION_REASON_DEVICE_ALARMING_STATE_CHANGE: AlarmSupervisorTrait.AlarmSupervisorDecisionReason
    class AlarmSupervisorResponseType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ALARM_SUPERVISOR_RESPONSE_TYPE_UNSPECIFIED: _ClassVar[AlarmSupervisorTrait.AlarmSupervisorResponseType]
        ALARM_SUPERVISOR_RESPONSE_TYPE_SUCCESS: _ClassVar[AlarmSupervisorTrait.AlarmSupervisorResponseType]
        ALARM_SUPERVISOR_RESPONSE_TYPE_FAIL_ALREADY: _ClassVar[AlarmSupervisorTrait.AlarmSupervisorResponseType]
        ALARM_SUPERVISOR_RESPONSE_TYPE_FAIL_INTERNAL_ISSUES: _ClassVar[AlarmSupervisorTrait.AlarmSupervisorResponseType]
        ALARM_SUPERVISOR_RESPONSE_TYPE_UNAUTHORIZED_STATE_CHANGE: _ClassVar[AlarmSupervisorTrait.AlarmSupervisorResponseType]
    ALARM_SUPERVISOR_RESPONSE_TYPE_UNSPECIFIED: AlarmSupervisorTrait.AlarmSupervisorResponseType
    ALARM_SUPERVISOR_RESPONSE_TYPE_SUCCESS: AlarmSupervisorTrait.AlarmSupervisorResponseType
    ALARM_SUPERVISOR_RESPONSE_TYPE_FAIL_ALREADY: AlarmSupervisorTrait.AlarmSupervisorResponseType
    ALARM_SUPERVISOR_RESPONSE_TYPE_FAIL_INTERNAL_ISSUES: AlarmSupervisorTrait.AlarmSupervisorResponseType
    ALARM_SUPERVISOR_RESPONSE_TYPE_UNAUTHORIZED_STATE_CHANGE: AlarmSupervisorTrait.AlarmSupervisorResponseType
    class AlarmSupervisorStateChangeEvent(_message.Message):
        __slots__ = ("priorAlarmingState", "alarmingState", "deviceAlarmReason", "alarmSupervisorReason", "triggeringActor")
        PRIORALARMINGSTATE_FIELD_NUMBER: _ClassVar[int]
        ALARMINGSTATE_FIELD_NUMBER: _ClassVar[int]
        DEVICEALARMREASON_FIELD_NUMBER: _ClassVar[int]
        ALARMSUPERVISORREASON_FIELD_NUMBER: _ClassVar[int]
        TRIGGERINGACTOR_FIELD_NUMBER: _ClassVar[int]
        priorAlarmingState: AlarmSupervisorTrait.AlarmSupervisorState
        alarmingState: AlarmSupervisorTrait.AlarmSupervisorState
        deviceAlarmReason: _containers.RepeatedCompositeFieldContainer[SecurityDecisionFact.SecurityDecisionFactStruct]
        alarmSupervisorReason: AlarmSupervisorTrait.AlarmSupervisorDecisionReason
        triggeringActor: SecurityActor.SecurityActorStruct
        def __init__(self, priorAlarmingState: _Optional[_Union[AlarmSupervisorTrait.AlarmSupervisorState, str]] = ..., alarmingState: _Optional[_Union[AlarmSupervisorTrait.AlarmSupervisorState, str]] = ..., deviceAlarmReason: _Optional[_Iterable[_Union[SecurityDecisionFact.SecurityDecisionFactStruct, _Mapping]]] = ..., alarmSupervisorReason: _Optional[_Union[AlarmSupervisorTrait.AlarmSupervisorDecisionReason, str]] = ..., triggeringActor: _Optional[_Union[SecurityActor.SecurityActorStruct, _Mapping]] = ...) -> None: ...
    class AlarmingAcknowledgeResponse(_message.Message):
        __slots__ = ("responseType",)
        RESPONSETYPE_FIELD_NUMBER: _ClassVar[int]
        responseType: AlarmSupervisorTrait.AlarmSupervisorResponseType
        def __init__(self, responseType: _Optional[_Union[AlarmSupervisorTrait.AlarmSupervisorResponseType, str]] = ...) -> None: ...
    class AlarmingAcknowledgeRequest(_message.Message):
        __slots__ = ("ackActor",)
        ACKACTOR_FIELD_NUMBER: _ClassVar[int]
        ackActor: SecurityActor.SecurityActorStruct
        def __init__(self, ackActor: _Optional[_Union[SecurityActor.SecurityActorStruct, _Mapping]] = ...) -> None: ...
    class SetPrealarmTimerResponse(_message.Message):
        __slots__ = ("responseType",)
        RESPONSETYPE_FIELD_NUMBER: _ClassVar[int]
        responseType: AlarmSupervisorTrait.AlarmSupervisorResponseType
        def __init__(self, responseType: _Optional[_Union[AlarmSupervisorTrait.AlarmSupervisorResponseType, str]] = ...) -> None: ...
    class SetPrealarmTimerRequest(_message.Message):
        __slots__ = ("reason",)
        REASON_FIELD_NUMBER: _ClassVar[int]
        reason: SecurityDecisionFact.SecurityDecisionFactStruct
        def __init__(self, reason: _Optional[_Union[SecurityDecisionFact.SecurityDecisionFactStruct, _Mapping]] = ...) -> None: ...
    class RemovePrealarmTimerResponse(_message.Message):
        __slots__ = ("responseType",)
        RESPONSETYPE_FIELD_NUMBER: _ClassVar[int]
        responseType: AlarmSupervisorTrait.AlarmSupervisorResponseType
        def __init__(self, responseType: _Optional[_Union[AlarmSupervisorTrait.AlarmSupervisorResponseType, str]] = ...) -> None: ...
    class RemovePrealarmTimerRequest(_message.Message):
        __slots__ = ("reason",)
        REASON_FIELD_NUMBER: _ClassVar[int]
        reason: SecurityDecisionFact.SecurityDecisionFactStruct
        def __init__(self, reason: _Optional[_Union[SecurityDecisionFact.SecurityDecisionFactStruct, _Mapping]] = ...) -> None: ...
    class RaiseAlarmResponse(_message.Message):
        __slots__ = ("responseType",)
        RESPONSETYPE_FIELD_NUMBER: _ClassVar[int]
        responseType: AlarmSupervisorTrait.AlarmSupervisorResponseType
        def __init__(self, responseType: _Optional[_Union[AlarmSupervisorTrait.AlarmSupervisorResponseType, str]] = ...) -> None: ...
    class RaiseAlarmRequest(_message.Message):
        __slots__ = ("reason",)
        REASON_FIELD_NUMBER: _ClassVar[int]
        reason: SecurityDecisionFact.SecurityDecisionFactStruct
        def __init__(self, reason: _Optional[_Union[SecurityDecisionFact.SecurityDecisionFactStruct, _Mapping]] = ...) -> None: ...
    ALARMSUPERVISORSTATE_FIELD_NUMBER: _ClassVar[int]
    ALARMINGSTATETIME_FIELD_NUMBER: _ClassVar[int]
    ALARMACKNOWLEDEGEACTOR_FIELD_NUMBER: _ClassVar[int]
    alarmSupervisorState: AlarmSupervisorTrait.AlarmSupervisorState
    alarmingStateTime: _timestamp_pb2.Timestamp
    alarmAcknowledegeActor: SecurityActor.SecurityActorStruct
    def __init__(self, alarmSupervisorState: _Optional[_Union[AlarmSupervisorTrait.AlarmSupervisorState, str]] = ..., alarmingStateTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., alarmAcknowledegeActor: _Optional[_Union[SecurityActor.SecurityActorStruct, _Mapping]] = ...) -> None: ...

class SecurityDecisionFact(_message.Message):
    __slots__ = ()
    class SecurityDecisionFactType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SECURITY_DECISION_FACT_TYPE_UNSPECIFIED: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_OPEN_DOOR: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_OPEN_DOOR_BYPASS: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_CLOSE_DOOR: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_OPEN_WINDOW: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_OPEN_WINDOW_BYPASS: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_CLOSE_WINDOW: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_AMBIENT_MOTION: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_HUB_AMBIENT_MOTION: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_HUB_DEVICE_MOVED: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_OFFLINE: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_ONLINE: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_HUB_OFFLINE: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_HUB_ONLINE: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_HUB_TAMPER: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_HUB_TAMPER_CLEARED: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_TAMPER: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_TAMPER_CLEARED: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_HUB_ONGOING_SOFTWARE_UPDATE: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_HUB_ONGOING_SOFTWARE_UPDATE_FINISHED: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_ONGOING_SOFTWARE_UPDATE: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_ONGOING_SOFTWARE_UPDATE_FINISHED: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_ACTIVE_JAMMING: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_ACTIVE_JAMMING_CLEARED: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_HUB_CHARGING_BATTERY: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_HUB_DISCHARGING_BATTERY_UNSAFE_LEVEL: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_HUB_DISCHARGING_BATTERY_SAFE_LEVEL: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_MULTIPLE_FAILED_AUTH_ATTEMPTS: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_HUB_BUTTON_PRESS: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_BUTTON_PRESS: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_BATTERY_NORMAL: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_BATTERY_LOW: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_BATTERY_CRITICALLY_LOW: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_THREAD_NETWORK_RESTORED: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_THREAD_NETWORK_DOWN: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_WIFI_NETWORK_RESTORED: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_WIFI_NETWORK_DOWN: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_CELLULAR_NETWORK_RESTORED: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_CELLULAR_NETWORK_DOWN: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_WEAVE_TUNNEL_RESTORED: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_WEAVE_TUNNEL_DOWN: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_PIR_HEAT_RAMP: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_PIR_HEAT_RAMP_CLEARED: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_HUB_HARDWARE_FAILURE: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_HUB_HARDWARE_FAILURE_CLEARED: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_HARDWARE_FAILURE: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_HARDWARE_FAILURE_CLEARED: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_PANIC_ALARM_IDLE: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_PANIC_ALARM_NOT_IDLE: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_CREDENTIALS_PROBLEM: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_CREDENTIALS_PROBLEM_CLEARED: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_MISSED_CRITICAL_EVENTS: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_HUB_GLASS_BREAK: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_SOUND_CHECK_FAILURE: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
        SECURITY_DECISION_FACT_TYPE_SOUND_CHECK_FAILURE_CLEARED: _ClassVar[SecurityDecisionFact.SecurityDecisionFactType]
    SECURITY_DECISION_FACT_TYPE_UNSPECIFIED: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_OPEN_DOOR: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_OPEN_DOOR_BYPASS: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_CLOSE_DOOR: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_OPEN_WINDOW: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_OPEN_WINDOW_BYPASS: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_CLOSE_WINDOW: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_AMBIENT_MOTION: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_HUB_AMBIENT_MOTION: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_HUB_DEVICE_MOVED: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_OFFLINE: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_ONLINE: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_HUB_OFFLINE: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_HUB_ONLINE: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_HUB_TAMPER: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_HUB_TAMPER_CLEARED: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_TAMPER: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_TAMPER_CLEARED: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_HUB_ONGOING_SOFTWARE_UPDATE: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_HUB_ONGOING_SOFTWARE_UPDATE_FINISHED: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_ONGOING_SOFTWARE_UPDATE: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_ONGOING_SOFTWARE_UPDATE_FINISHED: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_ACTIVE_JAMMING: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_ACTIVE_JAMMING_CLEARED: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_HUB_CHARGING_BATTERY: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_HUB_DISCHARGING_BATTERY_UNSAFE_LEVEL: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_HUB_DISCHARGING_BATTERY_SAFE_LEVEL: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_MULTIPLE_FAILED_AUTH_ATTEMPTS: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_HUB_BUTTON_PRESS: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_BUTTON_PRESS: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_BATTERY_NORMAL: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_BATTERY_LOW: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_BATTERY_CRITICALLY_LOW: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_THREAD_NETWORK_RESTORED: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_THREAD_NETWORK_DOWN: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_WIFI_NETWORK_RESTORED: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_WIFI_NETWORK_DOWN: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_CELLULAR_NETWORK_RESTORED: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_CELLULAR_NETWORK_DOWN: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_WEAVE_TUNNEL_RESTORED: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_WEAVE_TUNNEL_DOWN: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_PIR_HEAT_RAMP: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_PIR_HEAT_RAMP_CLEARED: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_HUB_HARDWARE_FAILURE: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_HUB_HARDWARE_FAILURE_CLEARED: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_HARDWARE_FAILURE: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_REMOTE_SENSOR_HARDWARE_FAILURE_CLEARED: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_PANIC_ALARM_IDLE: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_PANIC_ALARM_NOT_IDLE: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_CREDENTIALS_PROBLEM: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_CREDENTIALS_PROBLEM_CLEARED: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_MISSED_CRITICAL_EVENTS: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_HUB_GLASS_BREAK: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_SOUND_CHECK_FAILURE: SecurityDecisionFact.SecurityDecisionFactType
    SECURITY_DECISION_FACT_TYPE_SOUND_CHECK_FAILURE_CLEARED: SecurityDecisionFact.SecurityDecisionFactType
    class SecurityDecisionFactStruct(_message.Message):
        __slots__ = ("factType", "originResourceId", "timestamp")
        FACTTYPE_FIELD_NUMBER: _ClassVar[int]
        ORIGINRESOURCEID_FIELD_NUMBER: _ClassVar[int]
        TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        factType: SecurityDecisionFact.SecurityDecisionFactType
        originResourceId: _common_pb2.ResourceId
        timestamp: _timestamp_pb2.Timestamp
        def __init__(self, factType: _Optional[_Union[SecurityDecisionFact.SecurityDecisionFactType, str]] = ..., originResourceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class SecurityAlarmingTrait(_message.Message):
    __slots__ = ("alarmingState", "alarmReason", "prealarmExpirationTime", "prealarmingDuration", "alarmingStateTime")
    class SecurityAlarmingState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SECURITY_ALARMING_STATE_UNSPECIFIED: _ClassVar[SecurityAlarmingTrait.SecurityAlarmingState]
        SECURITY_ALARMING_STATE_IDLE: _ClassVar[SecurityAlarmingTrait.SecurityAlarmingState]
        SECURITY_ALARMING_STATE_PREALARMING: _ClassVar[SecurityAlarmingTrait.SecurityAlarmingState]
        SECURITY_ALARMING_STATE_ALARMING: _ClassVar[SecurityAlarmingTrait.SecurityAlarmingState]
    SECURITY_ALARMING_STATE_UNSPECIFIED: SecurityAlarmingTrait.SecurityAlarmingState
    SECURITY_ALARMING_STATE_IDLE: SecurityAlarmingTrait.SecurityAlarmingState
    SECURITY_ALARMING_STATE_PREALARMING: SecurityAlarmingTrait.SecurityAlarmingState
    SECURITY_ALARMING_STATE_ALARMING: SecurityAlarmingTrait.SecurityAlarmingState
    class SecurityAlarmingStateChangeReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SECURITY_ALARMING_STATE_CHANGE_REASON_UNSPECIFIED: _ClassVar[SecurityAlarmingTrait.SecurityAlarmingStateChangeReason]
        SECURITY_ALARMING_STATE_CHANGE_REASON_CLEARED: _ClassVar[SecurityAlarmingTrait.SecurityAlarmingStateChangeReason]
        SECURITY_ALARMING_STATE_CHANGE_REASON_NEW_TRIGGER: _ClassVar[SecurityAlarmingTrait.SecurityAlarmingStateChangeReason]
        SECURITY_ALARMING_STATE_CHANGE_REASON_TIMED_TRANSITION: _ClassVar[SecurityAlarmingTrait.SecurityAlarmingStateChangeReason]
        SECURITY_ALARMING_STATE_CHANGE_REASON_RESUMED: _ClassVar[SecurityAlarmingTrait.SecurityAlarmingStateChangeReason]
    SECURITY_ALARMING_STATE_CHANGE_REASON_UNSPECIFIED: SecurityAlarmingTrait.SecurityAlarmingStateChangeReason
    SECURITY_ALARMING_STATE_CHANGE_REASON_CLEARED: SecurityAlarmingTrait.SecurityAlarmingStateChangeReason
    SECURITY_ALARMING_STATE_CHANGE_REASON_NEW_TRIGGER: SecurityAlarmingTrait.SecurityAlarmingStateChangeReason
    SECURITY_ALARMING_STATE_CHANGE_REASON_TIMED_TRANSITION: SecurityAlarmingTrait.SecurityAlarmingStateChangeReason
    SECURITY_ALARMING_STATE_CHANGE_REASON_RESUMED: SecurityAlarmingTrait.SecurityAlarmingStateChangeReason
    class SecurityAlarmingDecisionResult(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SECURITY_ALARMING_DECISION_RESULT_UNSPECIFIED: _ClassVar[SecurityAlarmingTrait.SecurityAlarmingDecisionResult]
        SECURITY_ALARMING_DECISION_RESULT_TRIGGERED_PREALARM: _ClassVar[SecurityAlarmingTrait.SecurityAlarmingDecisionResult]
        SECURITY_ALARMING_DECISION_RESULT_TRIGGERED_INSTANT_ALARM: _ClassVar[SecurityAlarmingTrait.SecurityAlarmingDecisionResult]
        SECURITY_ALARMING_DECISION_RESULT_RECONFIRMED_INTRUSION: _ClassVar[SecurityAlarmingTrait.SecurityAlarmingDecisionResult]
        SECURITY_ALARMING_DECISION_RESULT_NO_ACTION: _ClassVar[SecurityAlarmingTrait.SecurityAlarmingDecisionResult]
    SECURITY_ALARMING_DECISION_RESULT_UNSPECIFIED: SecurityAlarmingTrait.SecurityAlarmingDecisionResult
    SECURITY_ALARMING_DECISION_RESULT_TRIGGERED_PREALARM: SecurityAlarmingTrait.SecurityAlarmingDecisionResult
    SECURITY_ALARMING_DECISION_RESULT_TRIGGERED_INSTANT_ALARM: SecurityAlarmingTrait.SecurityAlarmingDecisionResult
    SECURITY_ALARMING_DECISION_RESULT_RECONFIRMED_INTRUSION: SecurityAlarmingTrait.SecurityAlarmingDecisionResult
    SECURITY_ALARMING_DECISION_RESULT_NO_ACTION: SecurityAlarmingTrait.SecurityAlarmingDecisionResult
    class SecurityAlarmingStateChangeEvent(_message.Message):
        __slots__ = ("alarmingState", "priorAlarmingState", "initialAlarmReason", "securityArmSessionId", "changeReason", "latestAlarmReason")
        ALARMINGSTATE_FIELD_NUMBER: _ClassVar[int]
        PRIORALARMINGSTATE_FIELD_NUMBER: _ClassVar[int]
        INITIALALARMREASON_FIELD_NUMBER: _ClassVar[int]
        SECURITYARMSESSIONID_FIELD_NUMBER: _ClassVar[int]
        CHANGEREASON_FIELD_NUMBER: _ClassVar[int]
        LATESTALARMREASON_FIELD_NUMBER: _ClassVar[int]
        alarmingState: SecurityAlarmingTrait.SecurityAlarmingState
        priorAlarmingState: SecurityAlarmingTrait.SecurityAlarmingState
        initialAlarmReason: SecurityDecisionFact.SecurityDecisionFactStruct
        securityArmSessionId: int
        changeReason: SecurityAlarmingTrait.SecurityAlarmingStateChangeReason
        latestAlarmReason: SecurityDecisionFact.SecurityDecisionFactStruct
        def __init__(self, alarmingState: _Optional[_Union[SecurityAlarmingTrait.SecurityAlarmingState, str]] = ..., priorAlarmingState: _Optional[_Union[SecurityAlarmingTrait.SecurityAlarmingState, str]] = ..., initialAlarmReason: _Optional[_Union[SecurityDecisionFact.SecurityDecisionFactStruct, _Mapping]] = ..., securityArmSessionId: _Optional[int] = ..., changeReason: _Optional[_Union[SecurityAlarmingTrait.SecurityAlarmingStateChangeReason, str]] = ..., latestAlarmReason: _Optional[_Union[SecurityDecisionFact.SecurityDecisionFactStruct, _Mapping]] = ...) -> None: ...
    class SecurityAlarmingSetToIdleEvent(_message.Message):
        __slots__ = ("alarmActor", "priorAlarmingState", "securityArmSessionId", "alarmReasons")
        ALARMACTOR_FIELD_NUMBER: _ClassVar[int]
        PRIORALARMINGSTATE_FIELD_NUMBER: _ClassVar[int]
        SECURITYARMSESSIONID_FIELD_NUMBER: _ClassVar[int]
        ALARMREASONS_FIELD_NUMBER: _ClassVar[int]
        alarmActor: SecurityActor.SecurityActorStruct
        priorAlarmingState: SecurityAlarmingTrait.SecurityAlarmingState
        securityArmSessionId: int
        alarmReasons: _containers.RepeatedCompositeFieldContainer[SecurityDecisionFact.SecurityDecisionFactStruct]
        def __init__(self, alarmActor: _Optional[_Union[SecurityActor.SecurityActorStruct, _Mapping]] = ..., priorAlarmingState: _Optional[_Union[SecurityAlarmingTrait.SecurityAlarmingState, str]] = ..., securityArmSessionId: _Optional[int] = ..., alarmReasons: _Optional[_Iterable[_Union[SecurityDecisionFact.SecurityDecisionFactStruct, _Mapping]]] = ...) -> None: ...
    class SecurityAlarmingDecisionEvent(_message.Message):
        __slots__ = ("decisionFact", "result", "securityArmSessionId", "resultingState")
        DECISIONFACT_FIELD_NUMBER: _ClassVar[int]
        RESULT_FIELD_NUMBER: _ClassVar[int]
        SECURITYARMSESSIONID_FIELD_NUMBER: _ClassVar[int]
        RESULTINGSTATE_FIELD_NUMBER: _ClassVar[int]
        decisionFact: SecurityDecisionFact.SecurityDecisionFactStruct
        result: SecurityAlarmingTrait.SecurityAlarmingDecisionResult
        securityArmSessionId: int
        resultingState: SecurityAlarmingTrait.SecurityAlarmingState
        def __init__(self, decisionFact: _Optional[_Union[SecurityDecisionFact.SecurityDecisionFactStruct, _Mapping]] = ..., result: _Optional[_Union[SecurityAlarmingTrait.SecurityAlarmingDecisionResult, str]] = ..., securityArmSessionId: _Optional[int] = ..., resultingState: _Optional[_Union[SecurityAlarmingTrait.SecurityAlarmingState, str]] = ...) -> None: ...
    ALARMINGSTATE_FIELD_NUMBER: _ClassVar[int]
    ALARMREASON_FIELD_NUMBER: _ClassVar[int]
    PREALARMEXPIRATIONTIME_FIELD_NUMBER: _ClassVar[int]
    PREALARMINGDURATION_FIELD_NUMBER: _ClassVar[int]
    ALARMINGSTATETIME_FIELD_NUMBER: _ClassVar[int]
    alarmingState: SecurityAlarmingTrait.SecurityAlarmingState
    alarmReason: _containers.RepeatedCompositeFieldContainer[SecurityDecisionFact.SecurityDecisionFactStruct]
    prealarmExpirationTime: _timestamp_pb2.Timestamp
    prealarmingDuration: _duration_pb2.Duration
    alarmingStateTime: _timestamp_pb2.Timestamp
    def __init__(self, alarmingState: _Optional[_Union[SecurityAlarmingTrait.SecurityAlarmingState, str]] = ..., alarmReason: _Optional[_Iterable[_Union[SecurityDecisionFact.SecurityDecisionFactStruct, _Mapping]]] = ..., prealarmExpirationTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., prealarmingDuration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., alarmingStateTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class SecuritySettingsTrait(_message.Message):
    __slots__ = ("bypassFeatureEnabled", "petRejectionEnabled", "motionDetectionEnabled", "securitySettingsMode", "automaticallyArmOnScheduledNight")
    class SecuritySettingsMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SECURITY_SETTINGS_MODE_UNSPECIFIED: _ClassVar[SecuritySettingsTrait.SecuritySettingsMode]
        SECURITY_SETTINGS_MODE_NEST: _ClassVar[SecuritySettingsTrait.SecuritySettingsMode]
        SECURITY_SETTINGS_MODE_UL_CERT: _ClassVar[SecuritySettingsTrait.SecuritySettingsMode]
        SECURITY_SETTINGS_MODE_EU_CERT: _ClassVar[SecuritySettingsTrait.SecuritySettingsMode]
        SECURITY_SETTINGS_MODE_UK_CERT: _ClassVar[SecuritySettingsTrait.SecuritySettingsMode]
    SECURITY_SETTINGS_MODE_UNSPECIFIED: SecuritySettingsTrait.SecuritySettingsMode
    SECURITY_SETTINGS_MODE_NEST: SecuritySettingsTrait.SecuritySettingsMode
    SECURITY_SETTINGS_MODE_UL_CERT: SecuritySettingsTrait.SecuritySettingsMode
    SECURITY_SETTINGS_MODE_EU_CERT: SecuritySettingsTrait.SecuritySettingsMode
    SECURITY_SETTINGS_MODE_UK_CERT: SecuritySettingsTrait.SecuritySettingsMode
    class LimitedSettingsAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        LIMITED_SETTINGS_ACTION_UNSPECIFIED: _ClassVar[SecuritySettingsTrait.LimitedSettingsAction]
        LIMITED_SETTINGS_ACTION_ON: _ClassVar[SecuritySettingsTrait.LimitedSettingsAction]
        LIMITED_SETTINGS_ACTION_OFF: _ClassVar[SecuritySettingsTrait.LimitedSettingsAction]
    LIMITED_SETTINGS_ACTION_UNSPECIFIED: SecuritySettingsTrait.LimitedSettingsAction
    LIMITED_SETTINGS_ACTION_ON: SecuritySettingsTrait.LimitedSettingsAction
    LIMITED_SETTINGS_ACTION_OFF: SecuritySettingsTrait.LimitedSettingsAction
    class SecuritySettingsModeChangeEvent(_message.Message):
        __slots__ = ("previousSecuritySettingsMode", "newSecuritySettingsMode", "setToDefaults")
        PREVIOUSSECURITYSETTINGSMODE_FIELD_NUMBER: _ClassVar[int]
        NEWSECURITYSETTINGSMODE_FIELD_NUMBER: _ClassVar[int]
        SETTODEFAULTS_FIELD_NUMBER: _ClassVar[int]
        previousSecuritySettingsMode: SecuritySettingsTrait.SecuritySettingsMode
        newSecuritySettingsMode: SecuritySettingsTrait.SecuritySettingsMode
        setToDefaults: bool
        def __init__(self, previousSecuritySettingsMode: _Optional[_Union[SecuritySettingsTrait.SecuritySettingsMode, str]] = ..., newSecuritySettingsMode: _Optional[_Union[SecuritySettingsTrait.SecuritySettingsMode, str]] = ..., setToDefaults: bool = ...) -> None: ...
    class SecuritySettingsModeChangeRequest(_message.Message):
        __slots__ = ("securitySettingsMode", "setToDefaults")
        SECURITYSETTINGSMODE_FIELD_NUMBER: _ClassVar[int]
        SETTODEFAULTS_FIELD_NUMBER: _ClassVar[int]
        securitySettingsMode: SecuritySettingsTrait.SecuritySettingsMode
        setToDefaults: bool
        def __init__(self, securitySettingsMode: _Optional[_Union[SecuritySettingsTrait.SecuritySettingsMode, str]] = ..., setToDefaults: bool = ...) -> None: ...
    class ResetIntrusionSettingsByModeRequest(_message.Message):
        __slots__ = ("state",)
        STATE_FIELD_NUMBER: _ClassVar[int]
        state: SecurityArmTrait.SecurityArmState
        def __init__(self, state: _Optional[_Union[SecurityArmTrait.SecurityArmState, str]] = ...) -> None: ...
    class LimitedSettingsChangeRequest(_message.Message):
        __slots__ = ("action",)
        ACTION_FIELD_NUMBER: _ClassVar[int]
        action: SecuritySettingsTrait.LimitedSettingsAction
        def __init__(self, action: _Optional[_Union[SecuritySettingsTrait.LimitedSettingsAction, str]] = ...) -> None: ...
    BYPASSFEATUREENABLED_FIELD_NUMBER: _ClassVar[int]
    PETREJECTIONENABLED_FIELD_NUMBER: _ClassVar[int]
    MOTIONDETECTIONENABLED_FIELD_NUMBER: _ClassVar[int]
    SECURITYSETTINGSMODE_FIELD_NUMBER: _ClassVar[int]
    AUTOMATICALLYARMONSCHEDULEDNIGHT_FIELD_NUMBER: _ClassVar[int]
    bypassFeatureEnabled: bool
    petRejectionEnabled: bool
    motionDetectionEnabled: bool
    securitySettingsMode: SecuritySettingsTrait.SecuritySettingsMode
    automaticallyArmOnScheduledNight: bool
    def __init__(self, bypassFeatureEnabled: bool = ..., petRejectionEnabled: bool = ..., motionDetectionEnabled: bool = ..., securitySettingsMode: _Optional[_Union[SecuritySettingsTrait.SecuritySettingsMode, str]] = ..., automaticallyArmOnScheduledNight: bool = ...) -> None: ...

class SecurityActor(_message.Message):
    __slots__ = ()
    class SecurityActorMethod(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SECURITY_ACTOR_METHOD_UNSPECIFIED: _ClassVar[SecurityActor.SecurityActorMethod]
        SECURITY_ACTOR_METHOD_OTHER: _ClassVar[SecurityActor.SecurityActorMethod]
        SECURITY_ACTOR_METHOD_KEYPAD: _ClassVar[SecurityActor.SecurityActorMethod]
        SECURITY_ACTOR_METHOD_KEYPAD_PIN: _ClassVar[SecurityActor.SecurityActorMethod]
        SECURITY_ACTOR_METHOD_AUTH_TOKEN: _ClassVar[SecurityActor.SecurityActorMethod]
        SECURITY_ACTOR_METHOD_REMOTE_USER_EXPLICIT: _ClassVar[SecurityActor.SecurityActorMethod]
        SECURITY_ACTOR_METHOD_REMOTE_USER_IMPLICIT: _ClassVar[SecurityActor.SecurityActorMethod]
        SECURITY_ACTOR_METHOD_REMOTE_REMINDER_EXPLICIT: _ClassVar[SecurityActor.SecurityActorMethod]
        SECURITY_ACTOR_METHOD_REMOTE_REMINDER_IMPLICIT: _ClassVar[SecurityActor.SecurityActorMethod]
        SECURITY_ACTOR_METHOD_REMOTE_USER_OTHER: _ClassVar[SecurityActor.SecurityActorMethod]
        SECURITY_ACTOR_METHOD_REMOTE_DELEGATE: _ClassVar[SecurityActor.SecurityActorMethod]
        SECURITY_ACTOR_METHOD_LOW_POWER_SHUTDOWN: _ClassVar[SecurityActor.SecurityActorMethod]
        SECURITY_ACTOR_METHOD_VOICE_ASSISTANT: _ClassVar[SecurityActor.SecurityActorMethod]
        SECURITY_ACTOR_METHOD_PEER_LOCK: _ClassVar[SecurityActor.SecurityActorMethod]
        SECURITY_ACTOR_METHOD_REMOTE_SCHEDULE_IMPLICIT: _ClassVar[SecurityActor.SecurityActorMethod]
    SECURITY_ACTOR_METHOD_UNSPECIFIED: SecurityActor.SecurityActorMethod
    SECURITY_ACTOR_METHOD_OTHER: SecurityActor.SecurityActorMethod
    SECURITY_ACTOR_METHOD_KEYPAD: SecurityActor.SecurityActorMethod
    SECURITY_ACTOR_METHOD_KEYPAD_PIN: SecurityActor.SecurityActorMethod
    SECURITY_ACTOR_METHOD_AUTH_TOKEN: SecurityActor.SecurityActorMethod
    SECURITY_ACTOR_METHOD_REMOTE_USER_EXPLICIT: SecurityActor.SecurityActorMethod
    SECURITY_ACTOR_METHOD_REMOTE_USER_IMPLICIT: SecurityActor.SecurityActorMethod
    SECURITY_ACTOR_METHOD_REMOTE_REMINDER_EXPLICIT: SecurityActor.SecurityActorMethod
    SECURITY_ACTOR_METHOD_REMOTE_REMINDER_IMPLICIT: SecurityActor.SecurityActorMethod
    SECURITY_ACTOR_METHOD_REMOTE_USER_OTHER: SecurityActor.SecurityActorMethod
    SECURITY_ACTOR_METHOD_REMOTE_DELEGATE: SecurityActor.SecurityActorMethod
    SECURITY_ACTOR_METHOD_LOW_POWER_SHUTDOWN: SecurityActor.SecurityActorMethod
    SECURITY_ACTOR_METHOD_VOICE_ASSISTANT: SecurityActor.SecurityActorMethod
    SECURITY_ACTOR_METHOD_PEER_LOCK: SecurityActor.SecurityActorMethod
    SECURITY_ACTOR_METHOD_REMOTE_SCHEDULE_IMPLICIT: SecurityActor.SecurityActorMethod
    class SecurityActorStruct(_message.Message):
        __slots__ = ("method", "originator", "agent")
        METHOD_FIELD_NUMBER: _ClassVar[int]
        ORIGINATOR_FIELD_NUMBER: _ClassVar[int]
        AGENT_FIELD_NUMBER: _ClassVar[int]
        method: SecurityActor.SecurityActorMethod
        originator: _common_pb2.ResourceId
        agent: _common_pb2.ResourceId
        def __init__(self, method: _Optional[_Union[SecurityActor.SecurityActorMethod, str]] = ..., originator: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., agent: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class PanicAlarmingTrait(_message.Message):
    __slots__ = ("panicAlarmingState", "panicAlarmActor", "panicTime")
    class PanicAlarmingState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        PANIC_ALARMING_STATE_UNSPECIFIED: _ClassVar[PanicAlarmingTrait.PanicAlarmingState]
        PANIC_ALARMING_STATE_IDLE: _ClassVar[PanicAlarmingTrait.PanicAlarmingState]
        PANIC_ALARMING_STATE_PREPANIC: _ClassVar[PanicAlarmingTrait.PanicAlarmingState]
        PANIC_ALARMING_STATE_PANIC: _ClassVar[PanicAlarmingTrait.PanicAlarmingState]
    PANIC_ALARMING_STATE_UNSPECIFIED: PanicAlarmingTrait.PanicAlarmingState
    PANIC_ALARMING_STATE_IDLE: PanicAlarmingTrait.PanicAlarmingState
    PANIC_ALARMING_STATE_PREPANIC: PanicAlarmingTrait.PanicAlarmingState
    PANIC_ALARMING_STATE_PANIC: PanicAlarmingTrait.PanicAlarmingState
    class PanicAlarmingStateResponseType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        PANIC_ALARMING_STATE_RESPONSE_TYPE_UNSPECIFIED: _ClassVar[PanicAlarmingTrait.PanicAlarmingStateResponseType]
        PANIC_ALARMING_STATE_RESPONSE_TYPE_SUCCESS: _ClassVar[PanicAlarmingTrait.PanicAlarmingStateResponseType]
        PANIC_ALARMING_STATE_RESPONSE_TYPE_FAIL_ALREADY: _ClassVar[PanicAlarmingTrait.PanicAlarmingStateResponseType]
        PANIC_ALARMING_STATE_RESPONSE_TYPE_FAIL_INVALID_STATE_REQUEST: _ClassVar[PanicAlarmingTrait.PanicAlarmingStateResponseType]
    PANIC_ALARMING_STATE_RESPONSE_TYPE_UNSPECIFIED: PanicAlarmingTrait.PanicAlarmingStateResponseType
    PANIC_ALARMING_STATE_RESPONSE_TYPE_SUCCESS: PanicAlarmingTrait.PanicAlarmingStateResponseType
    PANIC_ALARMING_STATE_RESPONSE_TYPE_FAIL_ALREADY: PanicAlarmingTrait.PanicAlarmingStateResponseType
    PANIC_ALARMING_STATE_RESPONSE_TYPE_FAIL_INVALID_STATE_REQUEST: PanicAlarmingTrait.PanicAlarmingStateResponseType
    class PanicAlarmingStateRequest(_message.Message):
        __slots__ = ("targetPanicAlarmingState", "panicAlarmActor")
        TARGETPANICALARMINGSTATE_FIELD_NUMBER: _ClassVar[int]
        PANICALARMACTOR_FIELD_NUMBER: _ClassVar[int]
        targetPanicAlarmingState: PanicAlarmingTrait.PanicAlarmingState
        panicAlarmActor: SecurityActor.SecurityActorStruct
        def __init__(self, targetPanicAlarmingState: _Optional[_Union[PanicAlarmingTrait.PanicAlarmingState, str]] = ..., panicAlarmActor: _Optional[_Union[SecurityActor.SecurityActorStruct, _Mapping]] = ...) -> None: ...
    class PanicAlarmingStateResponse(_message.Message):
        __slots__ = ("responseType",)
        RESPONSETYPE_FIELD_NUMBER: _ClassVar[int]
        responseType: PanicAlarmingTrait.PanicAlarmingStateResponseType
        def __init__(self, responseType: _Optional[_Union[PanicAlarmingTrait.PanicAlarmingStateResponseType, str]] = ...) -> None: ...
    class PanicAlarmingStateChangeEvent(_message.Message):
        __slots__ = ("panicAlarmingState", "priorPanicAlarmingState", "panicAlarmActor")
        PANICALARMINGSTATE_FIELD_NUMBER: _ClassVar[int]
        PRIORPANICALARMINGSTATE_FIELD_NUMBER: _ClassVar[int]
        PANICALARMACTOR_FIELD_NUMBER: _ClassVar[int]
        panicAlarmingState: PanicAlarmingTrait.PanicAlarmingState
        priorPanicAlarmingState: PanicAlarmingTrait.PanicAlarmingState
        panicAlarmActor: SecurityActor.SecurityActorStruct
        def __init__(self, panicAlarmingState: _Optional[_Union[PanicAlarmingTrait.PanicAlarmingState, str]] = ..., priorPanicAlarmingState: _Optional[_Union[PanicAlarmingTrait.PanicAlarmingState, str]] = ..., panicAlarmActor: _Optional[_Union[SecurityActor.SecurityActorStruct, _Mapping]] = ...) -> None: ...
    PANICALARMINGSTATE_FIELD_NUMBER: _ClassVar[int]
    PANICALARMACTOR_FIELD_NUMBER: _ClassVar[int]
    PANICTIME_FIELD_NUMBER: _ClassVar[int]
    panicAlarmingState: PanicAlarmingTrait.PanicAlarmingState
    panicAlarmActor: SecurityActor.SecurityActorStruct
    panicTime: _timestamp_pb2.Timestamp
    def __init__(self, panicAlarmingState: _Optional[_Union[PanicAlarmingTrait.PanicAlarmingState, str]] = ..., panicAlarmActor: _Optional[_Union[SecurityActor.SecurityActorStruct, _Mapping]] = ..., panicTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class SecurityIssuesAndExceptionsTrait(_message.Message):
    __slots__ = ("blockingIssueSet", "nonblockingIssueSet", "exceptionSet")
    class SecurityBlockingIssuesChangeEvent(_message.Message):
        __slots__ = ("blockingIssueSet",)
        BLOCKINGISSUESET_FIELD_NUMBER: _ClassVar[int]
        blockingIssueSet: _containers.RepeatedCompositeFieldContainer[SecurityDecisionFact.SecurityDecisionFactStruct]
        def __init__(self, blockingIssueSet: _Optional[_Iterable[_Union[SecurityDecisionFact.SecurityDecisionFactStruct, _Mapping]]] = ...) -> None: ...
    class SecurityNonBlockingIssuesChangeEvent(_message.Message):
        __slots__ = ("nonblockingIssueSet",)
        NONBLOCKINGISSUESET_FIELD_NUMBER: _ClassVar[int]
        nonblockingIssueSet: _containers.RepeatedCompositeFieldContainer[SecurityDecisionFact.SecurityDecisionFactStruct]
        def __init__(self, nonblockingIssueSet: _Optional[_Iterable[_Union[SecurityDecisionFact.SecurityDecisionFactStruct, _Mapping]]] = ...) -> None: ...
    class SecurityExceptionsChangeEvent(_message.Message):
        __slots__ = ("exceptionSet",)
        EXCEPTIONSET_FIELD_NUMBER: _ClassVar[int]
        exceptionSet: _containers.RepeatedCompositeFieldContainer[SecurityDecisionFact.SecurityDecisionFactStruct]
        def __init__(self, exceptionSet: _Optional[_Iterable[_Union[SecurityDecisionFact.SecurityDecisionFactStruct, _Mapping]]] = ...) -> None: ...
    class SecurityNewIssuesByEndOfAllowanceEvent(_message.Message):
        __slots__ = ("issueSet",)
        ISSUESET_FIELD_NUMBER: _ClassVar[int]
        issueSet: _containers.RepeatedCompositeFieldContainer[SecurityDecisionFact.SecurityDecisionFactStruct]
        def __init__(self, issueSet: _Optional[_Iterable[_Union[SecurityDecisionFact.SecurityDecisionFactStruct, _Mapping]]] = ...) -> None: ...
    BLOCKINGISSUESET_FIELD_NUMBER: _ClassVar[int]
    NONBLOCKINGISSUESET_FIELD_NUMBER: _ClassVar[int]
    EXCEPTIONSET_FIELD_NUMBER: _ClassVar[int]
    blockingIssueSet: _containers.RepeatedCompositeFieldContainer[SecurityDecisionFact.SecurityDecisionFactStruct]
    nonblockingIssueSet: _containers.RepeatedCompositeFieldContainer[SecurityDecisionFact.SecurityDecisionFactStruct]
    exceptionSet: _containers.RepeatedCompositeFieldContainer[SecurityDecisionFact.SecurityDecisionFactStruct]
    def __init__(self, blockingIssueSet: _Optional[_Iterable[_Union[SecurityDecisionFact.SecurityDecisionFactStruct, _Mapping]]] = ..., nonblockingIssueSet: _Optional[_Iterable[_Union[SecurityDecisionFact.SecurityDecisionFactStruct, _Mapping]]] = ..., exceptionSet: _Optional[_Iterable[_Union[SecurityDecisionFact.SecurityDecisionFactStruct, _Mapping]]] = ...) -> None: ...

class SecurityIntrusionSettingsTrait(_message.Message):
    __slots__ = ("ambientMotionForIntrusionEnabled", "customIntrusionRules")
    class IntrusionAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        INTRUSION_ACTION_UNSPECIFIED: _ClassVar[SecurityIntrusionSettingsTrait.IntrusionAction]
        INTRUSION_ACTION_NONE: _ClassVar[SecurityIntrusionSettingsTrait.IntrusionAction]
        INTRUSION_ACTION_PREALARM: _ClassVar[SecurityIntrusionSettingsTrait.IntrusionAction]
        INTRUSION_ACTION_INSTANTALARM: _ClassVar[SecurityIntrusionSettingsTrait.IntrusionAction]
    INTRUSION_ACTION_UNSPECIFIED: SecurityIntrusionSettingsTrait.IntrusionAction
    INTRUSION_ACTION_NONE: SecurityIntrusionSettingsTrait.IntrusionAction
    INTRUSION_ACTION_PREALARM: SecurityIntrusionSettingsTrait.IntrusionAction
    INTRUSION_ACTION_INSTANTALARM: SecurityIntrusionSettingsTrait.IntrusionAction
    class ExpandedSecurityState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        EXPANDED_SECURITY_STATE_UNSPECIFIED: _ClassVar[SecurityIntrusionSettingsTrait.ExpandedSecurityState]
        EXPANDED_SECURITY_STATE_DISARMED: _ClassVar[SecurityIntrusionSettingsTrait.ExpandedSecurityState]
        EXPANDED_SECURITY_STATE_ARMED_SL1: _ClassVar[SecurityIntrusionSettingsTrait.ExpandedSecurityState]
        EXPANDED_SECURITY_STATE_ARMED_SL1_NOT_IDLE: _ClassVar[SecurityIntrusionSettingsTrait.ExpandedSecurityState]
        EXPANDED_SECURITY_STATE_ARMED_SL2_IN_EXIT_ALLOWANCE: _ClassVar[SecurityIntrusionSettingsTrait.ExpandedSecurityState]
        EXPANDED_SECURITY_STATE_ARMED_SL2: _ClassVar[SecurityIntrusionSettingsTrait.ExpandedSecurityState]
        EXPANDED_SECURITY_STATE_ARMED_SL2_NOT_IDLE: _ClassVar[SecurityIntrusionSettingsTrait.ExpandedSecurityState]
    EXPANDED_SECURITY_STATE_UNSPECIFIED: SecurityIntrusionSettingsTrait.ExpandedSecurityState
    EXPANDED_SECURITY_STATE_DISARMED: SecurityIntrusionSettingsTrait.ExpandedSecurityState
    EXPANDED_SECURITY_STATE_ARMED_SL1: SecurityIntrusionSettingsTrait.ExpandedSecurityState
    EXPANDED_SECURITY_STATE_ARMED_SL1_NOT_IDLE: SecurityIntrusionSettingsTrait.ExpandedSecurityState
    EXPANDED_SECURITY_STATE_ARMED_SL2_IN_EXIT_ALLOWANCE: SecurityIntrusionSettingsTrait.ExpandedSecurityState
    EXPANDED_SECURITY_STATE_ARMED_SL2: SecurityIntrusionSettingsTrait.ExpandedSecurityState
    EXPANDED_SECURITY_STATE_ARMED_SL2_NOT_IDLE: SecurityIntrusionSettingsTrait.ExpandedSecurityState
    class CustomIntrusionRulesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: SecurityIntrusionSettingsTrait.CustomIntrusionRule
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[SecurityIntrusionSettingsTrait.CustomIntrusionRule, _Mapping]] = ...) -> None: ...
    class CustomIntrusionRule(_message.Message):
        __slots__ = ("deviceId", "state", "factType", "action")
        DEVICEID_FIELD_NUMBER: _ClassVar[int]
        STATE_FIELD_NUMBER: _ClassVar[int]
        FACTTYPE_FIELD_NUMBER: _ClassVar[int]
        ACTION_FIELD_NUMBER: _ClassVar[int]
        deviceId: _common_pb2.ResourceId
        state: SecurityIntrusionSettingsTrait.ExpandedSecurityState
        factType: SecurityDecisionFact.SecurityDecisionFactType
        action: SecurityIntrusionSettingsTrait.IntrusionAction
        def __init__(self, deviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., state: _Optional[_Union[SecurityIntrusionSettingsTrait.ExpandedSecurityState, str]] = ..., factType: _Optional[_Union[SecurityDecisionFact.SecurityDecisionFactType, str]] = ..., action: _Optional[_Union[SecurityIntrusionSettingsTrait.IntrusionAction, str]] = ...) -> None: ...
    AMBIENTMOTIONFORINTRUSIONENABLED_FIELD_NUMBER: _ClassVar[int]
    CUSTOMINTRUSIONRULES_FIELD_NUMBER: _ClassVar[int]
    ambientMotionForIntrusionEnabled: bool
    customIntrusionRules: _containers.MessageMap[int, SecurityIntrusionSettingsTrait.CustomIntrusionRule]
    def __init__(self, ambientMotionForIntrusionEnabled: bool = ..., customIntrusionRules: _Optional[_Mapping[int, SecurityIntrusionSettingsTrait.CustomIntrusionRule]] = ...) -> None: ...

class SecurityActionOnUnlockSettingsTrait(_message.Message):
    __slots__ = ("enabled", "action")
    class SecurityAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SECURITY_ACTION_UNSPECIFIED: _ClassVar[SecurityActionOnUnlockSettingsTrait.SecurityAction]
        SECURITY_ACTION_DISARM_TO_SL0: _ClassVar[SecurityActionOnUnlockSettingsTrait.SecurityAction]
    SECURITY_ACTION_UNSPECIFIED: SecurityActionOnUnlockSettingsTrait.SecurityAction
    SECURITY_ACTION_DISARM_TO_SL0: SecurityActionOnUnlockSettingsTrait.SecurityAction
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    enabled: bool
    action: SecurityActionOnUnlockSettingsTrait.SecurityAction
    def __init__(self, enabled: bool = ..., action: _Optional[_Union[SecurityActionOnUnlockSettingsTrait.SecurityAction, str]] = ...) -> None: ...

class SecurityAlarmingSettingsTrait(_message.Message):
    __slots__ = ("prealarmingDuration", "prealarmingDurationSl1", "customPrealarmDurationRules", "advancedModeExceptions")
    class CustomPrealarmDurationRulesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: SecurityAlarmingSettingsTrait.CustomPreAlarmRule
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[SecurityAlarmingSettingsTrait.CustomPreAlarmRule, _Mapping]] = ...) -> None: ...
    class CustomPreAlarmRule(_message.Message):
        __slots__ = ("deviceId", "state", "factType", "prealarmDuration")
        DEVICEID_FIELD_NUMBER: _ClassVar[int]
        STATE_FIELD_NUMBER: _ClassVar[int]
        FACTTYPE_FIELD_NUMBER: _ClassVar[int]
        PREALARMDURATION_FIELD_NUMBER: _ClassVar[int]
        deviceId: _common_pb2.ResourceId
        state: SecurityArmTrait.SecurityArmState
        factType: SecurityDecisionFact.SecurityDecisionFactType
        prealarmDuration: _duration_pb2.Duration
        def __init__(self, deviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., state: _Optional[_Union[SecurityArmTrait.SecurityArmState, str]] = ..., factType: _Optional[_Union[SecurityDecisionFact.SecurityDecisionFactType, str]] = ..., prealarmDuration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...
    PREALARMINGDURATION_FIELD_NUMBER: _ClassVar[int]
    PREALARMINGDURATIONSL1_FIELD_NUMBER: _ClassVar[int]
    CUSTOMPREALARMDURATIONRULES_FIELD_NUMBER: _ClassVar[int]
    ADVANCEDMODEEXCEPTIONS_FIELD_NUMBER: _ClassVar[int]
    prealarmingDuration: _duration_pb2.Duration
    prealarmingDurationSl1: _duration_pb2.Duration
    customPrealarmDurationRules: _containers.MessageMap[int, SecurityAlarmingSettingsTrait.CustomPreAlarmRule]
    advancedModeExceptions: _containers.RepeatedScalarFieldContainer[SecurityDecisionFact.SecurityDecisionFactType]
    def __init__(self, prealarmingDuration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., prealarmingDurationSl1: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., customPrealarmDurationRules: _Optional[_Mapping[int, SecurityAlarmingSettingsTrait.CustomPreAlarmRule]] = ..., advancedModeExceptions: _Optional[_Iterable[_Union[SecurityDecisionFact.SecurityDecisionFactType, str]]] = ...) -> None: ...

class SecurityOpenCloseTrait(_message.Message):
    __slots__ = ("openCloseState", "firstObservedAt", "firstObservedAtMs", "bypassRequested")
    class SecurityOpenCloseEvent(_message.Message):
        __slots__ = ("openCloseState", "priorOpenCloseState", "bypassRequested")
        OPENCLOSESTATE_FIELD_NUMBER: _ClassVar[int]
        PRIOROPENCLOSESTATE_FIELD_NUMBER: _ClassVar[int]
        BYPASSREQUESTED_FIELD_NUMBER: _ClassVar[int]
        openCloseState: _detector_pb2.OpenCloseTrait.OpenCloseState
        priorOpenCloseState: _detector_pb2.OpenCloseTrait.OpenCloseState
        bypassRequested: bool
        def __init__(self, openCloseState: _Optional[_Union[_detector_pb2.OpenCloseTrait.OpenCloseState, str]] = ..., priorOpenCloseState: _Optional[_Union[_detector_pb2.OpenCloseTrait.OpenCloseState, str]] = ..., bypassRequested: bool = ...) -> None: ...
    OPENCLOSESTATE_FIELD_NUMBER: _ClassVar[int]
    FIRSTOBSERVEDAT_FIELD_NUMBER: _ClassVar[int]
    FIRSTOBSERVEDATMS_FIELD_NUMBER: _ClassVar[int]
    BYPASSREQUESTED_FIELD_NUMBER: _ClassVar[int]
    openCloseState: _detector_pb2.OpenCloseTrait.OpenCloseState
    firstObservedAt: _timestamp_pb2.Timestamp
    firstObservedAtMs: _timestamp_pb2.Timestamp
    bypassRequested: bool
    def __init__(self, openCloseState: _Optional[_Union[_detector_pb2.OpenCloseTrait.OpenCloseState, str]] = ..., firstObservedAt: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., firstObservedAtMs: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., bypassRequested: bool = ...) -> None: ...

class DistributedSecurityTrait(_message.Message):
    __slots__ = ("master",)
    MASTER_FIELD_NUMBER: _ClassVar[int]
    master: _common_pb2.ResourceId
    def __init__(self, master: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...

class EnhancedBoltLockSettingsTrait(_message.Message):
    __slots__ = ("autoRelockOn", "autoRelockDuration", "ignoreAutoRelockOnStructureMode", "oneTouchLock", "homeAwayAssistLockOn")
    AUTORELOCKON_FIELD_NUMBER: _ClassVar[int]
    AUTORELOCKDURATION_FIELD_NUMBER: _ClassVar[int]
    IGNOREAUTORELOCKONSTRUCTUREMODE_FIELD_NUMBER: _ClassVar[int]
    ONETOUCHLOCK_FIELD_NUMBER: _ClassVar[int]
    HOMEAWAYASSISTLOCKON_FIELD_NUMBER: _ClassVar[int]
    autoRelockOn: bool
    autoRelockDuration: _duration_pb2.Duration
    ignoreAutoRelockOnStructureMode: _containers.RepeatedScalarFieldContainer[_occupancy_pb2.StructureModeTrait.StructureMode]
    oneTouchLock: bool
    homeAwayAssistLockOn: bool
    def __init__(self, autoRelockOn: bool = ..., autoRelockDuration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., ignoreAutoRelockOnStructureMode: _Optional[_Iterable[_Union[_occupancy_pb2.StructureModeTrait.StructureMode, str]]] = ..., oneTouchLock: bool = ..., homeAwayAssistLockOn: bool = ...) -> None: ...

class SecurityActionOnNFCTokenGlobalSettingsTrait(_message.Message):
    __slots__ = ("featureEnabled",)
    FEATUREENABLED_FIELD_NUMBER: _ClassVar[int]
    featureEnabled: bool
    def __init__(self, featureEnabled: bool = ...) -> None: ...

class SecurityActionOnNFCTokenSettingsTrait(_message.Message):
    __slots__ = ("featureEnabled",)
    FEATUREENABLED_FIELD_NUMBER: _ClassVar[int]
    featureEnabled: bool
    def __init__(self, featureEnabled: bool = ...) -> None: ...

class SecurityArmCommandSettingsTrait(_message.Message):
    __slots__ = ("timeout",)
    TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    timeout: _duration_pb2.Duration
    def __init__(self, timeout: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class SecurityArmSettingsTrait(_message.Message):
    __slots__ = ("exitAllowanceDuration", "armingRequiresAuth", "ignoringIssuesRequiresAuth", "structureModeLinkingEnabled", "disarmOnDoorUnlock")
    EXITALLOWANCEDURATION_FIELD_NUMBER: _ClassVar[int]
    ARMINGREQUIRESAUTH_FIELD_NUMBER: _ClassVar[int]
    IGNORINGISSUESREQUIRESAUTH_FIELD_NUMBER: _ClassVar[int]
    STRUCTUREMODELINKINGENABLED_FIELD_NUMBER: _ClassVar[int]
    DISARMONDOORUNLOCK_FIELD_NUMBER: _ClassVar[int]
    exitAllowanceDuration: _duration_pb2.Duration
    armingRequiresAuth: bool
    ignoringIssuesRequiresAuth: bool
    structureModeLinkingEnabled: bool
    disarmOnDoorUnlock: bool
    def __init__(self, exitAllowanceDuration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., armingRequiresAuth: bool = ..., ignoringIssuesRequiresAuth: bool = ..., structureModeLinkingEnabled: bool = ..., disarmOnDoorUnlock: bool = ...) -> None: ...
