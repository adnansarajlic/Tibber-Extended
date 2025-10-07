# Kör tester lokalt

## Installera beroenden
cd /path/to/tibber-extended
pip install -r tests/requirements.txt

## Kör alla tester
pytest tests/ -v

## Kör specifikt test
pytest tests/test_sensor.py::test_sensor_creation -v

## Kör med coverage
pytest tests/ --cov=custom_components/tibber_extended --cov-report=html
