"""Provider codes for the mandatory ``data_source`` column."""

DATA_SOURCES = {
    "forecastex_csv": "ForecastEx public CSV downloads (prices, pairs, summary)",
    "ibkr_tws": "IBKR TWS/Gateway quote capture on the owner's device",
    "fred": "FRED REST API",
    "alfred": "ALFRED vintage REST API",
    "frb_speech": "federalreserve.gov speeches feed",
    "frb_sep": "federalreserve.gov Summary of Economic Projections pages",
    "frb_other": "Other federalreserve.gov documents (statements, minutes, Beige Book)",
    "bls": "BLS release pages",
    "cleveland_fed": "Cleveland Fed inflation nowcast",
    "gdelt": "GDELT",
}
