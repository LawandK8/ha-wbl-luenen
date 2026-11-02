"""Live tests against wbl.de (need internet)."""

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

DOMAIN = "wbl_luenen"


async def _start(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_street_only_flow_and_entities(hass, socket_enabled):
    r = await _start(hass)
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"street": "gibtsnicht"})
    assert r["errors"] == {"street": "street_not_found"}

    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"street": "achenbachstr."})
    assert r["step_id"] == "bins", r
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"bins": []})
    assert r["errors"] == {"base": "no_bins"}
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"bins": ["Graue-Tonne", "Bio-Tonne", "Gelbe-Tonne", "Blaue-Tonne"]}
    )
    assert r["type"] is FlowResultType.CREATE_ENTRY, r
    assert r["title"] == "Achenbachstraße"
    await hass.async_block_till_done()

    states = {s.entity_id: s for s in hass.states.async_all()}
    for entity_id, state in sorted(states.items()):
        print(entity_id, state.state, dict(state.attributes))
    bins = [e for e in states if e.startswith("sensor.") and "next_collection" not in e]
    assert len(bins) == 4
    nxt = next(s for e, s in states.items() if e.endswith("next_collection"))
    assert " · " in nxt.state

    # Options: switch to the red bin only -> reload with one bin sensor.
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    r = await hass.config_entries.options.async_init(entry.entry_id)
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"bins": ["Rote-Tonne"]})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.runtime_data.bins == ["Rote-Tonne"]
    assert list(entry.runtime_data.data) == ["Rote-Tonne"]


async def test_split_street_offers_dropdown(hass, socket_enabled):
    r = await _start(hass)
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"street": "Ahornstraße"})
    assert r["step_id"] == "street", r
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"street": "Ahornstraße 1-13 und 2-18"}
    )
    assert r["step_id"] == "bins"
