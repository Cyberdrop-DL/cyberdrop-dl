import pytest

from cyberdrop_dl.crawlers.vk import full_res_img
from cyberdrop_dl.url_objects import AbsoluteHttpURL


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://sun6-20.userapi.com/impf/dwZBZfHK80GDEqLBNrFkQ7_vkJqzPYozqgBzRw/Q8GeTduRtKc.jpg?size=2048x1152&quality=95&blur=50,20&sign=fd23dc0bd9d62c90342b298f6d16a2f1e2&type=album",
            "https://pp.userapi.com/dwZBZfHK80GDEqLBNrFkQ7_vkJqzPYozqgBzRw/Q8GeTduRtKc.jpg",
        ),
        (
            "https://sun6-22.userapi.com/impg/Y2CnE6t5b0OjEXAfKhXGVdrULCcBhzCqei8xFw/fJaaw1koXDo.jpg?size=2023x1138&quality=95&sign=423df1007f18a6860a322a2b1c9f2032b0",
            "https://pp.userapi.com/Y2CnE6t5b0OjEXAfKhXGVdrULCcBhzCqei8xFw/fJaaw1koXDo.jpg",
        ),
    ],
)
def test_full_res_img(url: str, expected: str) -> None:
    result = full_res_img(AbsoluteHttpURL(url))
    assert str(result) == expected
