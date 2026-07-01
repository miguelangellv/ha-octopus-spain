"""Octopus Spain API."""

from datetime import datetime

from python_graphql_client import GraphqlClient

GRAPH_QL_ENDPOINT = "https://api.oees-kraken.energy/v1/graphql/"
SOLAR_WALLET_LEDGER = "SOLAR_WALLET_LEDGER"
ELECTRICITY_LEDGER = "SPAIN_ELECTRICITY_LEDGER"

# The API caps the readings page size at 100 (a larger `first` returns
# "Invalid pagination parameters"). We paginate with `after`/`endCursor`. With
# 100 nodes per request we also stay well below the 10,000-node limit
# (KT-CT-1189). A 12-month backfill (~8760 h) is ~88 requests per flow.
READINGS_PAGE = 100


class OctopusApiError(Exception):
    """Error returned by the Octopus GraphQL API (a response with `errors`)."""


class OctopusSpain:
    """Octopus Spain API."""

    def __init__(self, email, password):
        self._email = email
        self._password = password
        self._token = None

    async def login(self):
        """Login to Octopus Spain API."""
        mutation = """
           mutation obtainKrakenToken($input: ObtainJSONWebTokenInput!) {
              obtainKrakenToken(input: $input) {
                token
              }
            }
        """
        variables = {"input": {"email": self._email, "password": self._password}}

        client = GraphqlClient(endpoint=GRAPH_QL_ENDPOINT)
        response = await client.execute_async(mutation, variables)

        if "errors" in response:
            return False

        self._token = response["data"]["obtainKrakenToken"]["token"]
        return True

    async def accounts(self):
        """Get account names from Octopus Spain API."""

        query = """
             query getAccountNames{
                viewer {
                    accounts {
                        ... on Account {
                            number
                        }
                    }
                }
            }
            """

        headers = {"authorization": self._token}
        client = GraphqlClient(endpoint=GRAPH_QL_ENDPOINT, headers=headers)
        response = await client.execute_async(query)

        return list(map(lambda a: a["number"], response["data"]["viewer"]["accounts"]))

    async def cups(self, account: str):
        """Get the electricity CUPS identifiers of an account."""
        query = """
            query ($account: String!) {
              account(accountNumber: $account) {
                properties { electricitySupplyPoints { cups } }
              }
            }
        """
        headers = {"authorization": self._token}
        client = GraphqlClient(endpoint=GRAPH_QL_ENDPOINT, headers=headers)
        response = await client.execute_async(query, {"account": account})
        result = []
        for prop in response["data"]["account"]["properties"] or []:
            for spp in prop.get("electricitySupplyPoints", []) or []:
                if spp.get("cups"):
                    result.append(spp["cups"])
        return result

    async def readings(self, account: str, start, end, granularity: str = "HOUR"):
        """Get import (consumption) and export readings between start and end.

        Each flow is paginated separately to respect the API node limit.
        """
        return {
            "import": await self._fetch_connection(account, start, end, granularity, "importReadings"),
            "export": await self._fetch_connection(account, start, end, granularity, "exportReadings"),
        }

    async def _fetch_connection(self, account: str, start, end, granularity: str, field: str):
        """Paginate one readings connection (importReadings or exportReadings)."""
        query = (
            """
            query ($account: String!, $start: DateTime!, $end: DateTime!, $granularity: TimeGranularities, $first: Int!, $after: String) {
              supplyPoints(accountNumber: $account) {
                edges { node {
                  readings(startAt: $start, endAt: $end, readingType: INTERVAL,
                           timeGranularity: $granularity, timezone: "Europe/Madrid", units: [KILOWATT_HOURS]) {
                    %s(first: $first, after: $after) {
                      pageInfo { hasNextPage endCursor }
                      edges { node { value units intervalStart intervalEnd } }
                    }
                  }
                } }
              }
            }
        """
            % field
        )

        client = GraphqlClient(endpoint=GRAPH_QL_ENDPOINT, headers={"authorization": self._token})
        results = []
        cursor = None
        while True:
            response = await client.execute_async(
                query,
                {
                    "account": account,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "granularity": granularity,
                    "first": READINGS_PAGE,
                    "after": cursor,
                },
            )
            if not response.get("data"):
                raise OctopusApiError(self._error_message(response))
            edges = response["data"]["supplyPoints"]["edges"]
            if not edges:
                return []
            connection = edges[0]["node"]["readings"].get(field)
            if connection is None:
                raise OctopusApiError(self._error_message(response))
            results.extend(self._parse_readings(connection["edges"]))
            if not connection["pageInfo"]["hasNextPage"]:
                return results
            cursor = connection["pageInfo"]["endCursor"]

    @staticmethod
    def _error_message(response: dict) -> str:
        errors = response.get("errors") or []
        if errors:
            return "; ".join(e.get("message", "") for e in errors)
        return "Octopus API returned no data"

    @staticmethod
    def _parse_readings(edges):
        """Convert GraphQL reading edges into [{start, end, value}] (kWh)."""
        out = []
        for e in edges:
            n = e["node"]
            if n.get("value") is None:
                continue
            if n.get("units") not in (None, "KILOWATT_HOURS"):
                continue
            out.append(
                {
                    "start": datetime.fromisoformat(n["intervalStart"]),
                    "end": datetime.fromisoformat(n["intervalEnd"]),
                    "value": float(n["value"]),
                }
            )
        return out

    async def account(self, account: str):
        """Get account data from Octopus Spain API."""

        query = """
            query ($account: String!) {
              accountBillingInfo(accountNumber: $account) {
                ledgers {
                  ledgerType
                  balance
                }
              }
              account(accountNumber: $account) {
                bills(first: 1) {
                  edges {
                    node {
                      issuedDate
                      fromDate
                      toDate
                      ... on InvoiceType {
                        grossAmount
                      }
                    }
                  }
                }
                properties {
                  electricitySupplyPoints {
                    activeAgreement {
                      product {
                        prices(decimalPlaces: 6) {
                          variableTerm
                          variableTermWithTaxes
                          surplusRate
                        }
                      }
                    }
                  }
                }
              }
            }
        """
        headers = {"authorization": self._token}
        client = GraphqlClient(endpoint=GRAPH_QL_ENDPOINT, headers=headers)
        response = await client.execute_async(query, {"account": account})
        data = response["data"]
        ledgers = data["accountBillingInfo"]["ledgers"]
        electricity = next(filter(lambda x: x["ledgerType"] == ELECTRICITY_LEDGER, ledgers), None)
        solar_wallet = next(filter(lambda x: x["ledgerType"] == SOLAR_WALLET_LEDGER, ledgers), {"balance": 0})

        if not electricity:
            raise ValueError("Electricity ledger not found")

        bills = data.get("account", {}).get("bills", {}).get("edges", [])

        if len(bills) == 0:
            last_invoice = {"amount": None, "issued": None, "start": None, "end": None}
        else:
            invoice = bills[0]["node"]
            last_invoice = {
                "amount": (float(invoice["grossAmount"]) / 100) if invoice.get("grossAmount") is not None else 0,
                "issued": datetime.fromisoformat(invoice["issuedDate"]).date(),
                "start": datetime.fromisoformat(invoice["fromDate"]).date(),
                "end": datetime.fromisoformat(invoice["toDate"]).date(),
            }

        return {
            "solar_wallet": (float(solar_wallet["balance"]) / 100),
            "octopus_credit": (float(electricity["balance"]) / 100),
            "last_invoice": last_invoice,
            "prices": self._prices(data.get("account", {})),
        }

    @staticmethod
    def _prices(account_data: dict):
        for prop in account_data.get("properties", []) or []:
            for spp in prop.get("electricitySupplyPoints", []) or []:
                product = (spp.get("activeAgreement") or {}).get("product") or {}
                prices = product.get("prices")
                if not prices:
                    continue
                variable = prices.get("variableTerm")
                with_taxes = prices.get("variableTermWithTaxes")
                if isinstance(variable, list) and len(variable) == 3:
                    has_taxes = isinstance(with_taxes, list) and len(with_taxes) == 3
                    return {
                        "peak": variable[0],
                        "standard": variable[1],
                        "valley": variable[2],
                        "peak_with_taxes": with_taxes[0] if has_taxes else None,
                        "standard_with_taxes": with_taxes[1] if has_taxes else None,
                        "valley_with_taxes": with_taxes[2] if has_taxes else None,
                        "surplus": prices.get("surplusRate"),
                    }
        return None
