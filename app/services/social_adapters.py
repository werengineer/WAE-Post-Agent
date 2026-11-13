"""One adapter per platform. Each builds the exact HTTP requests it would send
(`plan`) and can execute them (`publish`). Credentials come from the environment."""

import os
import re
from dataclasses import dataclass, field

import requests

TIMEOUT = 30
GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v21.0")


class PublishError(Exception):
    pass


@dataclass
class Call:
    method: str
    url: str
    json: dict | None = None
    data: dict | None = None
    headers: dict = field(default_factory=dict)


def _env(*names: str) -> dict:
    missing = [n for n in names if not os.getenv(n)]
    if missing:
        raise PublishError("Missing environment variables: " + ", ".join(missing))
    return {n: os.environ[n] for n in names}


def _post(call: Call) -> requests.Response:
    # No redirects and no automatic retries: a timeout may still have posted.
    resp = requests.post(call.url, json=call.json, data=call.data, headers=call.headers,
                         timeout=TIMEOUT, allow_redirects=False)
    if not 200 <= resp.status_code < 300:
        raise PublishError(f"{call.url.split('?')[0]} returned HTTP {resp.status_code}: {resp.text[:300]}")
    return resp


class Adapter:
    name = ""
    limit = 0
    requires_media = False

    def plan(self, post: dict) -> list[Call]:
        raise NotImplementedError

    def publish(self, post: dict) -> str:
        """Send the post live and return the platform's post id."""
        raise NotImplementedError


class LinkedIn(Adapter):
    name, limit = "linkedin", 3000
    # LinkedIn "little text" treats these as markup; '#' is left alone so hashtags work.
    _reserved = re.compile(r"([\\|{}@\[\]()<>*_~])")

    def plan(self, post):
        e = _env("LINKEDIN_ACCESS_TOKEN", "LINKEDIN_AUTHOR_URN")  # urn:li:organization:123
        return [Call("POST", "https://api.linkedin.com/rest/posts", json={
            "author": e["LINKEDIN_AUTHOR_URN"],
            "commentary": self._reserved.sub(r"\\\1", post["text"]),
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                             "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }, headers={
            "Authorization": f"Bearer {e['LINKEDIN_ACCESS_TOKEN']}",
            "LinkedIn-Version": os.getenv("LINKEDIN_API_VERSION", "202411"),
            "X-Restli-Protocol-Version": "2.0.0",
        })]

    def publish(self, post):
        resp = _post(self.plan(post)[0])
        return resp.headers.get("x-restli-id", "")


class X(Adapter):
    name, limit = "x", 280

    def plan(self, post):
        e = _env("X_ACCESS_TOKEN")  # OAuth 2.0 user-context token with tweet.write
        return [Call("POST", "https://api.x.com/2/tweets", json={"text": post["text"]},
                     headers={"Authorization": f"Bearer {e['X_ACCESS_TOKEN']}"})]

    def publish(self, post):
        return _post(self.plan(post)[0]).json().get("data", {}).get("id", "")


class Facebook(Adapter):
    name, limit = "facebook", 63206

    def plan(self, post):
        e = _env("FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_TOKEN")
        return [Call("POST", f"https://graph.facebook.com/{GRAPH_VERSION}/{e['FACEBOOK_PAGE_ID']}/feed",
                     data={"message": post["text"]},
                     headers={"Authorization": f"Bearer {e['FACEBOOK_PAGE_TOKEN']}"})]

    def publish(self, post):
        return _post(self.plan(post)[0]).json().get("id", "")


class Instagram(Adapter):
    name, limit, requires_media = "instagram", 2200, True

    def _calls(self, post, creation_id="<creation_id>"):
        e = _env("INSTAGRAM_USER_ID", "INSTAGRAM_ACCESS_TOKEN")
        image = post.get("image_url", "")
        if not image.startswith("https://"):
            raise PublishError("Instagram needs a public HTTPS 'image_url' in the draft")
        base = f"https://graph.facebook.com/{GRAPH_VERSION}/{e['INSTAGRAM_USER_ID']}"
        headers = {"Authorization": f"Bearer {e['INSTAGRAM_ACCESS_TOKEN']}"}
        return (Call("POST", f"{base}/media", data={"image_url": image, "caption": post["text"]}, headers=headers),
                Call("POST", f"{base}/media_publish", data={"creation_id": creation_id}, headers=headers))

    def plan(self, post):
        return list(self._calls(post))

    def publish(self, post):
        create, _ = self._calls(post)
        container = _post(create).json().get("id")
        if not container:
            raise PublishError("Instagram did not return a media container id")
        _, publish = self._calls(post, container)
        return _post(publish).json().get("id", "")


ADAPTERS = {a.name: a for a in (LinkedIn(), X(), Facebook(), Instagram())}


def get_adapter(platform: str) -> Adapter:
    try:
        return ADAPTERS[platform]
    except KeyError:
        raise PublishError(f"No adapter for platform: {platform}") from None
