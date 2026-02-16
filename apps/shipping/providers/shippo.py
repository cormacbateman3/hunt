import json
from urllib import error, parse, request
from django.conf import settings


class ShippoError(Exception):
    pass


class ShippoClient:
    def __init__(self):
        self.api_key = settings.SHIPPO_API_KEY
        self.base_url = settings.SHIPPO_API_BASE_URL.rstrip('/')

    def _headers(self):
        return {
            'Authorization': f'ShippoToken {self.api_key}',
            'Content-Type': 'application/json',
        }

    def _request(self, method, path, payload=None):
        if not self.api_key:
            raise ShippoError('Shippo API key is not configured.')

        url = f'{self.base_url}{path}'
        body = None
        if payload is not None:
            body = json.dumps(payload).encode('utf-8')

        req = request.Request(url, data=body, method=method, headers=self._headers())
        try:
            with request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except error.HTTPError as exc:
            try:
                details = exc.read().decode('utf-8')
            except Exception:
                details = str(exc)
            raise ShippoError(f'Shippo request failed ({exc.code}): {details}') from exc
        except error.URLError as exc:
            raise ShippoError(f'Shippo network error: {exc}') from exc

    def create_shipment(self, *, address_from, address_to, parcel):
        payload = {
            'address_from': address_from,
            'address_to': address_to,
            'parcels': [parcel],
            'async': False,
        }
        return self._request('POST', '/shipments/', payload=payload)

    def create_transaction(self, *, rate_id, label_file_type='PDF'):
        payload = {
            'rate': rate_id,
            'label_file_type': label_file_type,
            'async': False,
        }
        return self._request('POST', '/transactions/', payload=payload)

    def get_tracking_status(self, *, carrier, tracking_number):
        carrier_encoded = parse.quote(carrier, safe='')
        tracking_encoded = parse.quote(tracking_number, safe='')
        return self._request('GET', f'/tracks/{carrier_encoded}/{tracking_encoded}/')
