import re

with open('tests/test_lessons.py', 'r', encoding='utf-8') as f:
    text = f.read()

func = """

def test_clear_memory():
    g = icon()
    process_icon(g, Options(quality='fast'), name='c')
    s = LS.summary()
    assert s["icons"] >= 1
    res = LS.clear()
    assert res["log_cleared"] and res["stats_cleared"]
    s2 = LS.summary()
    assert s2["icons"] == 0
"""

if 'test_clear_memory' not in text:
    idx = text.rfind('if __name__')
    text = text[:idx] + func + "\n\n" + text[idx:]
    text = text.replace("test_set_widths_are_unified(); print('ok set widths unified')",
                        "test_set_widths_are_unified(); print('ok set widths unified')\n    test_clear_memory(); print('ok clear memory')")
    with open('tests/test_lessons.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Updated test_lessons.py")
else:
    print("Already present")
