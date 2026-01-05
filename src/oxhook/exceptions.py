class OxHookError(Exception):
    pass

class TopicNotFound(OxHookError):
    pass

class InvalidPayloadType(OxHookError):
    pass
