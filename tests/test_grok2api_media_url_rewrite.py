import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "_grok2api_rewrite_test_package"


def _load_backend_module():
    package = types.ModuleType(PACKAGE_NAME)
    package.__path__ = [str(ROOT / "core")]
    sys.modules[PACKAGE_NAME] = package

    astrbot = types.ModuleType("astrbot")
    astrbot_api = types.ModuleType("astrbot.api")
    astrbot_api.logger = types.SimpleNamespace(info=lambda *args, **kwargs: None)
    astrbot.api = astrbot_api
    sys.modules["astrbot"] = astrbot
    sys.modules["astrbot.api"] = astrbot_api

    image_format = types.ModuleType(f"{PACKAGE_NAME}.image_format")
    image_format.guess_image_mime_and_ext = lambda data: ("image/png", "png")
    sys.modules[image_format.__name__] = image_format

    compat = types.ModuleType(f"{PACKAGE_NAME}.openai_compat_backend")
    compat._build_collage = lambda images: images[0]
    compat.normalize_openai_compat_base_url = lambda value: value
    compat.resolution_to_size = lambda value: value
    sys.modules[compat.__name__] = compat

    output_spec = types.ModuleType(f"{PACKAGE_NAME}.output_spec")
    output_spec.OutputIntent = type("OutputIntent", (), {})
    sys.modules[output_spec.__name__] = output_spec

    module_name = f"{PACKAGE_NAME}.grok2api_images_backend"
    spec = importlib.util.spec_from_file_location(
        module_name, ROOT / "core" / "grok2api_images_backend.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_rewrites_loopback_origin_and_preserves_resource_parts():
    module = _load_backend_module()
    actual = module._rewrite_loopback_media_url(
        "http://127.0.0.1:8000/images/a.png?token=x#preview",
        provider_url="https://grok.example.com:9443/v1",
    )
    assert actual == "https://grok.example.com:9443/images/a.png?token=x#preview"


def test_rewrites_localhost_ipv4_and_ipv6_only():
    module = _load_backend_module()
    provider = "http://192.168.1.20:9000/v1"
    assert module._rewrite_loopback_media_url(
        "http://localhost:8000/a.png", provider_url=provider
    ) == "http://192.168.1.20:9000/a.png"
    assert module._rewrite_loopback_media_url(
        "http://[::1]:8000/a.png", provider_url=provider
    ) == "http://192.168.1.20:9000/a.png"
    assert module._rewrite_loopback_media_url(
        "https://cdn.example.com/a.png", provider_url=provider
    ) == "https://cdn.example.com/a.png"
    assert module._rewrite_loopback_media_url(
        "http://10.0.0.8/a.png", provider_url=provider
    ) == "http://10.0.0.8/a.png"


def test_invalid_provider_url_leaves_result_unchanged():
    module = _load_backend_module()
    ref = "http://127.0.0.1:8000/a.png"
    assert module._rewrite_loopback_media_url(ref, provider_url="") == ref
    assert module._rewrite_loopback_media_url(ref, provider_url="ftp://host") == ref
