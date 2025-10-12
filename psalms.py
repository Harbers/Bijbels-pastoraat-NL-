cd /root/bijbels-pastoraat-app

cat > psalms.py <<'PY'
# Schone proxy naar psalm_client
try:
    # geval 1: psalm_client exporteert functies
    from psalm_client import get_vers, get_max_vers
    class _Client:
        def get_vers(self, psalm: int, vers: int):
            return get_vers(psalm, vers)
        def get_max_vers(self, psalm: int):
            return get_max_vers(psalm)
    client = _Client()
except Exception:
    # geval 2: psalm_client exporteert een klasse
    from psalm_client import PsalmClient
    client = PsalmClient()
PY
