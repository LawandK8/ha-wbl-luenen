"""Constants for the WBL Abfallkalender integration."""

from datetime import timedelta

DOMAIN = "wbl_luenen"

CONF_STREET = "street"
CONF_BINS = "bins"

# Preselected in the setup dialog: the usual bins of a household.
DEFAULT_BINS = ["Graue-Tonne", "Rote-Tonne", "Gelbe-Tonne", "Bio-Tonne", "Blaue-Tonne"]

UPDATE_INTERVAL = timedelta(hours=12)

ATTRIBUTION = "Daten: Wirtschaftsbetriebe Lünen GmbH (WBL)"
