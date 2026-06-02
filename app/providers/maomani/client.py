import random
import time
import xml.etree.ElementTree as ET

import requests
from kbinxml import KBinXML

from app.providers.maomani.arc4 import EamuseARC4


DEFAULT_SERVER_URL = "http://maomani.cn:573"
DEFAULT_PCBID = "00010203040506070809"

INQUIRE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<call model="KFC:J:G:A:2025042202" srcid="{pcbid}" tag="11451419">
    <cardmng cardid="{card_no}" cardtype="1" method="inquire" update="0"/>
</call>"""

SCORE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<call model="KFC:J:G:A:2025042202" srcid="{pcbid}" tag="11451419">
    <game k="6b4805cc0b8a0ce65aaf62cbcf892e89" method="sv7_load_m" ver="0">
        <refid __type="str">{refid}</refid>
    </game>
</call>"""


class MaomaniClientError(RuntimeError):
    pass


class MaomaniClient:
    def __init__(self, server_url: str = DEFAULT_SERVER_URL, timeout: float = 15.0) -> None:
        if not server_url.startswith(("http://", "https://")):
            server_url = f"http://{server_url}"
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def get_refid(self, card_no: str, pcbid: str = DEFAULT_PCBID) -> str:
        xml = INQUIRE_TEMPLATE.format(pcbid=pcbid, card_no=card_no)
        response = self._send_request(xml, "/?model=KFC:J:G:A:2025052700&f=cardmng.inquire")
        root = ET.fromstring(response.encode("utf-8"))
        cardmng = root.find("cardmng")
        refid = cardmng.get("refid") if cardmng is not None else None
        if not refid:
            raise MaomaniClientError("failed to query card refid")
        return refid

    def get_scores(self, refid: str, pcbid: str = DEFAULT_PCBID) -> list[list[str]]:
        xml = SCORE_TEMPLATE.format(pcbid=pcbid, refid=refid)
        response = self._send_request(xml, "/?model=KFC:J:G:A:2025052700&f=game.sv7_load_m")
        root = ET.fromstring(response.encode("utf-8"))
        records: list[list[str]] = []

        for info in root.findall(".//info"):
            param = info.find("param")
            if param is not None and param.text:
                records.append(param.text.strip().split())

        if not records:
            raise MaomaniClientError("no score records found")
        return records

    def _send_request(self, xml_template: str, endpoint: str) -> str:
        eamuse_info = self._generate_eamuse_info()
        xml_data = KBinXML(xml_template.encode("utf-8")).to_binary()
        encrypted_data = self._encrypt_request(xml_data, eamuse_info)
        response = self.session.post(
            f"{self.server_url}{endpoint}",
            data=encrypted_data,
            headers={
                "X-Eamuse-Info": eamuse_info,
                "User-Agent": "EAMUSE.XRPC/1.0",
                "Content-Length": str(len(encrypted_data)),
                "X-Compress": "none",
            },
            timeout=self.timeout,
        )

        if response.status_code != 200:
            raise MaomaniClientError(f"maomani returned HTTP {response.status_code}")

        return self._decode_response(response)

    @staticmethod
    def _generate_eamuse_info() -> str:
        timestamp = int(time.time())
        random_part = random.randint(0x0000, 0xFFFF)
        return f"1-{timestamp:08x}-{random_part:04x}"

    @staticmethod
    def _encrypt_request(xml_data: bytes, eamuse_info: str) -> bytes:
        key = bytes.fromhex(eamuse_info[2:].replace("-", ""))
        return EamuseARC4(key).encrypt(xml_data)

    @staticmethod
    def _decode_response(response: requests.Response) -> str:
        response_eamuse_info = response.headers.get("X-Eamuse-Info")
        if response_eamuse_info:
            decrypt_key = bytes.fromhex(response_eamuse_info[2:].replace("-", ""))
            content = EamuseARC4(decrypt_key).decrypt(response.content)
        else:
            content = response.content

        try:
            readable_xml = KBinXML(content).to_text()
            if isinstance(readable_xml, bytes):
                return readable_xml.decode("utf-8")
            return readable_xml
        except Exception:
            return content.decode("utf-8", errors="ignore")
