__all__ = (
    'NOTHING',
    'VERSION_2_0',
)


class NOTHING:
    pass


VERSION_2_0 = '2.0'

EMPTY_VALUES = (None, NOTHING,)

JSON_PRIMITIVE_TYPES = (str, int, float, bool, type(None),)
