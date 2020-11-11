import base64
import binascii
import hashlib
import pathlib
from urllib.parse import parse_qs

import httpx


def get_player_id():
    player_id = base64.encodebytes(hashlib.sha1(b"").digest()).rstrip()
    return player_id.decode("ascii")


def extract_token_from_url(url):
    parsed_url = url.query
    query_dict = parse_qs(parsed_url)
    return query_dict["playerToken"]


def get_player_token(auth) -> str:
    audible_base_url = f"https://www.audible.{auth.locale.domain}"
    audible_token_url = audible_base_url + "/player-auth-token"

    params = {
        "ipRedirectOverride": True,
        "playerType": "software",
        "bp_ua": "y",
        "playerModel": "Desktop",
        "playerId": get_player_id(),
        "playerManufacturer": "Audible",
        "serial": ""
    }
    headers = {"auth_mode": "cookies"}

    with httpx.Client(auth=auth, headers=headers) as session:
        resp = session.get(audible_token_url, params=params)

    player_token = extract_token_from_url(resp.url)[0]
    return player_token


def extract_activation_bytes(data):
    if (b"BAD_LOGIN" in data or b"Whoops" in data) or \
            b"group_id" not in data:
        print(data)
        print("\nActivation failed! ;(")
        raise ValueError("data wrong")
    a = data.rfind(b"group_id")
    b = data[a:].find(b")")
    keys = data[a + b + 1 + 1:]
    output = []
    output_keys = []
    # each key is of 70 bytes
    for i in range(0, 8):
        key = keys[i * 70 + i:(i + 1) * 70 + i]
        h = binascii.hexlify(bytes(key))
        h = [h[i:i+2] for i in range(0, len(h), 2)]
        h = b','.join(h)
        output_keys.append(h)
        output.append(h.decode("utf-8"))

    # only 4 bytes of output_keys[0] are necessary for decryption! ;)
    activation_bytes = output_keys[0].replace(b",", b"")[0:8]
    # get the endianness right (reverse string in pairs of 2)
    activation_bytes = b"".join(reversed([activation_bytes[i:i+2] for i in
                                         range(0, len(activation_bytes), 2)]))
    activation_bytes = activation_bytes.decode("ascii")

    return activation_bytes, output


def fetch_activation_bytes(player_token, filename=None):
    register_url = "https://www.audible.com/license/licenseForCustomerToken"

    # register params
    register_params = {"customer_token": player_token}

    # deregister params
    deregister_params = {
        "customer_token": player_token,
        "action": "de-register"
    }

    headers = {"User-Agent": "Audible Download Manager"}
    with httpx.Client(headers=headers) as session:
        session.get(register_url, params=deregister_params)

        resp = session.get(register_url, params=register_params)
        if filename:
            pathlib.Path(filename).write_bytes(resp.content)
        activation_bytes, _ = extract_activation_bytes(resp.content)

        session.get(register_url, params=deregister_params)

        return activation_bytes


def get_activation_bytes(auth, filename=None):
    player_token = get_player_token(auth)
    activation_bytes = fetch_activation_bytes(player_token, filename)

    return activation_bytes
