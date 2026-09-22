from planning_center_mcp.propresenter import lyrics_from_pro

RTF_HEAD = (
    rb"{\rtf0\ansi\ansicpg1252{\fonttbl\f0\fnil Futura-Medium;}"
    rb"{\colortbl;\red255\green255\blue255;}{\*\listtable}\uc1\pard\fs48 "
)


def _pro(*slides: bytes) -> bytes:
    """A protobuf-ish blob with RTF blocks embedded, as ProPresenter writes them."""
    out = b"\n&\x08\x02\x12\x0f"
    for slide in slides:
        out += b"\x12\x08" + RTF_HEAD + slide + b"}" + b"\x18\x01"
    return out


class TestLyricsFromPro:
    def test_extracts_slide_text_in_order(self):
        text = lyrics_from_pro(_pro(rb"Come now is the time", rb"to worship"))
        assert text == "Come now is the time\n\nto worship"

    def test_par_breaks_lines_but_pard_does_not(self):
        text = lyrics_from_pro(_pro(rb"One day every tongue\par\pard\fs48 Will confess"))
        assert text == "One day every tongue\nWill confess"

    def test_decodes_unicode_and_hex_escapes(self):
        text = lyrics_from_pro(_pro(rb"Alegr\'eda \u237 \u8217 s"))
        assert text == "Alegría í’s"  # RTF eats one space after a control word

    def test_dedupes_repeated_slides(self):
        text = lyrics_from_pro(_pro(rb"Hallelujah", rb"Hallelujah", rb"Amen"))
        assert text == "Hallelujah\n\nAmen"

    def test_empty_template_yields_empty_string(self):
        assert lyrics_from_pro(_pro(rb"")) == ""

    def test_strips_nested_list_tables(self):
        nested = (rb"{\rtf0\ansi{\fonttbl\f0\fnil Futura;}"
                  rb"{\*\listtable{\list\listid1{\listlevel\levelnfc23{\leveltext \'01\'b7;}}}}"
                  rb"\uc1\pard\fs48 Dance the steps of joyful Zion}")
        assert lyrics_from_pro(b"\x12\x08" + nested) == "Dance the steps of joyful Zion"

    def test_file_without_rtf_yields_empty_string(self):
        assert lyrics_from_pro(b"\n&\x08\x02no rtf here") == ""
