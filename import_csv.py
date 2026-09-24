import csv
import sys

from app import add_lead, LeadIn


def main():
    if len(sys.argv) != 2:
        raise SystemExit("用法：python import_csv.py data/leads.csv")
    with open(sys.argv[1], newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            values = {
                "company": row["company"],
                "signal": row["signal"],
                "source_name": row.get("source_name") or "",
                "source_url": row.get("source_url") or "",
                "score": float(row.get("score") or 0),
            }
            if row.get("updated_at"):
                values["updated_at"] = row["updated_at"]
            lead = LeadIn(**values)
            result = add_lead(lead)
            print(f"导入线索 #{result['id']}：{lead.company}")


if __name__ == "__main__":
    main()
