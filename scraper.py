import os
import re
import time
import json
import logging
from datetime import datetime, timezone
import urllib.request
import urllib.error
import yaml

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bondscraper")

HEADERS = {
	"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
	"Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
}

BORSA_ITALIANA_PATTERNS = [
	"https://www.borsaitaliana.it/borsa/obbligazioni/mot/euro-obbligazioni/scheda/{isin}.html",
	"https://www.borsaitaliana.it/borsa/obbligazioni/mot/btp-bot-altri-titoli-di-stato/scheda/{isin}.html",
	"https://www.borsaitaliana.it/borsa/obbligazioni/mot/obbligazioni-euro-euroobbligazioni/scheda/{isin}.html",
	"https://www.borsaitaliana.it/borsa/obbligazioni/eurotlx/scheda/{isin}.html",
	"https://www.borsaitaliana.it/borsa/obbligazioni/eurotlx/altre-obbligazioni/scheda/{isin}.html",
]


def fetch_url(url: str) -> str:
	"""Fetch HTML content from a URL with cache-busting parameters and headers."""
	ts = int(time.time())
	delimiter = "&" if "?" in url else "?"
	cache_busting_url = f"{url}{delimiter}_nocache={ts}"
	headers = {
		**HEADERS,
		"Cache-Control": "no-cache, no-store, must-revalidate",
		"Pragma": "no-cache",
		"Expires": "0",
	}
	req = urllib.request.Request(cache_busting_url, headers=headers)
	with urllib.request.urlopen(req, timeout=15) as resp:
		return resp.read().decode("utf-8", errors="ignore")


def parse_italian_float(val_str: str) -> float:
	"""Convert Italian formatted number string (e.g. '102,32689') to float."""
	clean_str = val_str.strip().replace(".", "").replace(",", ".")
	return float(clean_str)


def extract_td_after_label(label: str, html_content: str) -> str:
	"""Extract content from a span or td following a specific label tag."""
	pattern = r'<strong>\s*' + re.escape(label) + r'\s*</strong>.*?<span[^>]*>(.*?)</span>'
	m = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
	if m:
		clean = re.sub(r'<[^>]+>', '', m.group(1)).strip()
		return clean
	return None


def parse_date_to_iso(date_str: str) -> str:
	"""Convert DD/MM/YY or DD/MM/YYYY or YYYY-MM-DD to ISO date string YYYY-MM-DDT00:00:00Z."""
	if not date_str:
		return datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")

	clean_date = date_str.strip()
	parts = clean_date.split("/")
	if len(parts) == 3:
		day, month, year = parts
		if len(year) == 2:
			year = "20" + year
		return f"{year}-{month.zfill(2)}-{day.zfill(2)}T00:00:00Z"

	try:
		dt = datetime.fromisoformat(clean_date.replace("Z", ""))
		return dt.strftime("%Y-%m-%dT00:00:00Z")
	except ValueError:
		return datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")


def scrape_borsa_italiana(isin: str, custom_url: str = None) -> tuple:
	"""Scrape quote from Borsa Italiana."""
	urls_to_try = []
	if custom_url:
		urls_to_try.append(custom_url)
	urls_to_try.extend([p.format(isin=isin) for p in BORSA_ITALIANA_PATTERNS])

	html = None
	successful_url = None

	for url in urls_to_try:
		try:
			logger.info(f"Fetching {isin} from {url}")
			html = fetch_url(url)
			if "Prezzo" in html or "Ultimo" in html or "Ufficiale" in html:
				successful_url = url
				break
		except urllib.error.HTTPError as err:
			if err.code == 404:
				continue
			logger.warning(f"HTTP Error {err.code} for {url}")
		except Exception as ex:
			logger.warning(f"Error fetching {url}: {ex}")

	if not html:
		raise ValueError(f"Could not fetch data for ISIN {isin} from any known Borsa Italiana URL.")

	# Priority 1: Prezzo di riferimento paired with Data di riferimento / Data Pr Riferimento
	ref_price_str = extract_td_after_label("Prezzo di riferimento", html)
	ref_date_str = extract_td_after_label("Data di riferimento", html) or extract_td_after_label("Data Pr Riferimento", html)

	if ref_price_str and ref_date_str:
		price = parse_italian_float(ref_price_str)
		iso_date = parse_date_to_iso(ref_date_str)
		return iso_date, price

	# Priority 2: Prezzo ufficiale paired with Data Pr Ufficiale
	off_price_str = extract_td_after_label("Prezzo ufficiale", html)
	off_date_str = extract_td_after_label("Data Pr Ufficiale", html)

	if off_price_str and off_date_str:
		price = parse_italian_float(off_price_str)
		iso_date = parse_date_to_iso(off_date_str)
		return iso_date, price

	# Priority 3: Ultimo prezzo
	last_price_str = extract_td_after_label("Ultimo prezzo", html) or extract_td_after_label("Ultimo", html)
	if last_price_str:
		price = parse_italian_float(last_price_str)
		iso_date = parse_date_to_iso(None)
		return iso_date, price

	raise ValueError(f"Could not locate price label in HTML for {isin} ({successful_url}).")


def scrape_custom(bond_cfg: dict) -> tuple:
	"""Scrape quote using custom regex selectors specified in bond configuration."""
	url = bond_cfg.get("url")
	if not url:
		raise ValueError(f"Custom provider for bond {bond_cfg.get('isin')} requires a 'url'.")

	html = fetch_url(url)
	selectors = bond_cfg.get("selectors", {})

	price_regex = selectors.get("price_regex")
	if price_regex:
		m = re.search(price_regex, html)
		if not m:
			raise ValueError(f"price_regex '{price_regex}' matched nothing on {url}")
		price_str = m.group(1)
	else:
		raise ValueError("Custom provider requires 'selectors.price_regex'.")

	date_regex = selectors.get("date_regex")
	if date_regex:
		m_date = re.search(date_regex, html)
		date_str = m_date.group(1) if m_date else None
	else:
		date_str = None

	price = parse_italian_float(price_str)
	iso_date = parse_date_to_iso(date_str)

	return iso_date, price


def update_bond_json(isin: str, new_date: str, new_price: float, out_dir: str = "out") -> dict:
	"""Merge new date & price into out/{isin}.json historical array."""
	os.makedirs(out_dir, exist_ok=True)
	filepath = os.path.join(out_dir, f"{isin}.json")

	quotes = []
	if os.path.exists(filepath):
		try:
			with open(filepath, "r", encoding="utf-8") as f:
				quotes = json.load(f)
		except Exception as ex:
			logger.warning(f"Could not read existing file {filepath}, starting fresh: {ex}")
			quotes = []

	is_changed = False
	existing_entry = next((q for q in quotes if q.get("date") == new_date), None)
	if existing_entry:
		if existing_entry.get("close") != new_price:
			logger.info(f"{isin}: Updating existing entry for {new_date} from {existing_entry.get('close')} to {new_price}")
			existing_entry["close"] = new_price
			is_changed = True
		else:
			logger.info(f"{isin}: Entry for {new_date} already up to date with close={new_price}")
	else:
		logger.info(f"{isin}: Appending new entry for {new_date} with close={new_price}")
		quotes.append({"date": new_date, "close": new_price})
		is_changed = True

	# Sort by date
	quotes.sort(key=lambda x: x["date"])

	with open(filepath, "w", encoding="utf-8") as f:
		json.dump(quotes, f, indent=2)

	return {
		"total_quotes": len(quotes),
		"latest_date": quotes[-1]["date"] if quotes else new_date,
		"latest_close": quotes[-1]["close"] if quotes else new_price,
		"is_changed": is_changed,
	}


def main():
	config_path = "bonds.json"
	if not os.path.exists(config_path):
		config_path = "bonds.yaml"

	if not os.path.exists(config_path):
		logger.error("Configuration file bonds.json or bonds.yaml not found!")
		return

	with open(config_path, "r", encoding="utf-8") as f:
		if config_path.endswith(".json"):
			config = json.load(f)
		else:
			config = yaml.safe_load(f)

	bonds = config.get("bonds", [])
	logger.info(f"Loaded {len(bonds)} bonds from {config_path}")

	summary = []
	any_bond_changed = False

	for bond in bonds:
		isin = bond.get("isin")
		name = bond.get("name", isin)
		provider = bond.get("provider", "borsa_italiana")
		url = bond.get("url")

		logger.info(f"--- Processing {name} ({isin}) ---")
		try:
			if provider == "borsa_italiana":
				iso_date, price = scrape_borsa_italiana(isin, custom_url=url)
			elif provider == "custom":
				iso_date, price = scrape_custom(bond)
			else:
				logger.error(f"Unknown provider '{provider}' for bond {isin}")
				continue

			res = update_bond_json(isin, iso_date, price)
			if res.get("is_changed"):
				any_bond_changed = True

			summary.append(
				{
					"isin": isin,
					"name": name,
					"provider": provider,
					"last_date": res["latest_date"],
					"last_close": res["latest_close"],
					"total_quotes": res["total_quotes"],
					"json_file": f"out/{isin}.json",
					"status": "success",
				}
			)
			logger.info(f"SUCCESS {isin}: Date={iso_date}, Close={price}")
		except Exception as ex:
			logger.error(f"FAILED {isin}: {ex}")
			summary.append(
				{
					"isin": isin,
					"name": name,
					"provider": provider,
					"status": "error",
					"error": str(ex),
				}
			)

	# Write summary index.json
	summary_path = os.path.join("out", "index.json")
	existing_updated_at = None

	if os.path.exists(summary_path):
		try:
			with open(summary_path, "r", encoding="utf-8") as f:
				old_summary = json.load(f)
				existing_updated_at = old_summary.get("updated_at")
		except Exception:
			existing_updated_at = None

	# Only update updated_at timestamp if actual bond prices changed or index.json doesn't exist
	if any_bond_changed or not existing_updated_at:
		updated_at_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
	else:
		updated_at_str = existing_updated_at

	with open(summary_path, "w", encoding="utf-8") as f:
		json.dump({"updated_at": updated_at_str, "bonds": summary}, f, indent="\t")
	logger.info(f"Wrote summary to {summary_path} (changed={any_bond_changed})")


if __name__ == "__main__":
	main()
