from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_rework_page_exposes_sn_disposition_and_controlled_actions():
    source = (ROOT / 'admin/static/js/pages/final1.js').read_text(encoding='utf-8')
    for text in ('处置单号', 'SN', '检测报告', '工序', '返工周期', '处置状态', '返工任务'):
        assert text in source
    for action in ('rework', 'scrap', 'concession', 'start-task'):
        assert action in source
    assert '/api/site/rework/add' not in source


def test_serial_page_maps_every_quality_status():
    source = (ROOT / 'admin/static/js/pages/prod_ext.js').read_text(encoding='utf-8')
    for status in ('normal', 'quality_hold', 'rework', 'scrapped', 'concession'):
        assert status in source


def test_machine_report_page_displays_disposition_state():
    source = (ROOT / 'admin/static/js/pages/machine_iot.js').read_text(encoding='utf-8')
    assert '处置单' in source
    assert 'disposition_status' in source
