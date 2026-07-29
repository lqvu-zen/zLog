"""Pure Windows Event Log XML parsing/mapping. No pywin32, no Qt, no display."""

from __future__ import annotations

from zlog.core.winevent import format_event_time, map_level, parse_event_xml

_NS = "http://schemas.microsoft.com/win/2004/08/events/event"


def _event_xml(
    *,
    provider="Application Error",
    event_id="1000",
    level="2",
    system_time="2026-07-29T10:15:23.1234567Z",
    pid="4321",
    tid="8765",
    data=("faulting application notepad.exe",),
    include_execution=True,
) -> str:
    exec_el = f'<Execution ProcessID="{pid}" ThreadID="{tid}" />' if include_execution else ""
    data_els = "".join(f"<Data>{d}</Data>" for d in data)
    return (
        f'<Event xmlns="{_NS}">'
        "<System>"
        f'<Provider Name="{provider}" />'
        f'<EventID Qualifiers="0">{event_id}</EventID>'
        f"<Level>{level}</Level>"
        f'<TimeCreated SystemTime="{system_time}" />'
        f"{exec_el}"
        "<Channel>Application</Channel>"
        "</System>"
        f"<EventData>{data_els}</EventData>"
        "</Event>"
    )


def test_map_level_known_values():
    assert map_level("1") == "F"
    assert map_level("2") == "E"
    assert map_level("3") == "W"
    assert map_level("4") == "I"
    assert map_level("5") == "V"
    assert map_level("0") == "I"


def test_map_level_unknown_or_missing_defaults_to_info():
    assert map_level("99") == "I"
    assert map_level(None) == "I"
    assert map_level("") == "I"


def test_format_event_time_matches_logcat_shape():
    assert format_event_time("2026-07-29T10:15:23.1234567Z") == "07-29 10:15:23.123"


def test_format_event_time_short_fraction_padded():
    assert format_event_time("2026-01-05T09:03:00.5Z") == "01-05 09:03:00.500"


def test_format_event_time_no_fraction():
    assert format_event_time("2026-01-05T09:03:00Z") == "01-05 09:03:00.000"


def test_format_event_time_garbage_is_empty():
    assert format_event_time("not a timestamp") == ""
    assert format_event_time("") == ""


def test_parse_event_xml_maps_all_fields():
    entry = parse_event_xml(_event_xml())
    assert entry.tag == "Application Error"
    assert entry.level == "E"
    assert entry.time == "07-29 10:15:23.123"
    assert entry.pid == "4321"
    assert entry.tid == "8765"
    assert entry.source == "evtlog"
    assert entry.message == "[1000] faulting application notepad.exe"


def test_parse_event_xml_no_event_data_falls_back_to_event_id():
    entry = parse_event_xml(_event_xml(data=()))
    assert entry.message == "Event 1000"


def test_parse_event_xml_missing_execution_defaults_to_empty_pid_tid():
    entry = parse_event_xml(_event_xml(include_execution=False))
    assert entry.pid == ""
    assert entry.tid == ""


def test_parse_event_xml_multiple_data_values_joined():
    entry = parse_event_xml(_event_xml(data=("first", "second")))
    assert entry.message == "[1000] first; second"


def test_parse_event_xml_missing_provider_falls_back_to_eventlog_tag():
    xml = (
        f'<Event xmlns="{_NS}"><System>'
        '<EventID Qualifiers="0">1</EventID><Level>4</Level>'
        '<TimeCreated SystemTime="2026-01-01T00:00:00Z" />'
        "</System><EventData /></Event>"
    )
    entry = parse_event_xml(xml)
    assert entry.tag == "EventLog"


def test_parse_event_xml_malformed_xml_degrades_to_raw_text():
    entry = parse_event_xml("<not><valid")
    assert entry.time == ""
    assert entry.pid == ""
    assert entry.level == ""
    assert entry.message == "<not><valid"


def test_parse_event_xml_missing_system_block_degrades_to_raw_text():
    xml = f'<Event xmlns="{_NS}"><EventData /></Event>'
    entry = parse_event_xml(xml)
    assert entry.level == ""
    assert entry.message == xml
