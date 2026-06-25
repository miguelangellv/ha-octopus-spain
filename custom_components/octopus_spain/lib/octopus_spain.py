from datetime import datetime

from python_graphql_client import GraphqlClient

GRAPH_QL_ENDPOINT = "https://api.oees-kraken.energy/v1/graphql/"
SOLAR_WALLET_LEDGER = "SOLAR_WALLET_LEDGER"
ELECTRICITY_LEDGER = "SPAIN_ELECTRICITY_LEDGER"


class OctopusSpain:
    def __init__(self, email, password):
        self._email = email
        self._password = password
        self._token = None

    async def login(self):
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

    async def account(self, account: str):
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
        electricity = next(filter(lambda x: x['ledgerType'] == ELECTRICITY_LEDGER, ledgers), None)
        solar_wallet = next(filter(lambda x: x['ledgerType'] == SOLAR_WALLET_LEDGER, ledgers), {'balance': 0})

        if not electricity:
            raise Exception("Electricity ledger not found")

        bills = data.get("account", {}).get("bills", {}).get("edges", [])

        if len(bills) == 0:
            last_invoice = {'amount': None, 'issued': None, 'start': None, 'end': None}
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
