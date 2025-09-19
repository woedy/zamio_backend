import csv
from django.core.management.base import BaseCommand, CommandError

from royalties.models import PartnerPRO, ExternalRecording, ExternalWork


class Command(BaseCommand):
    help = "Import partner repertoire from a simple CSV (partner_display_name,isrc,title,work_title,duration_seconds)"

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Path to CSV file")
        parser.add_argument("partner_id", type=int, help="PartnerPRO ID")
        parser.add_argument("--dry-run", action="store_true", help="Validate only; do not write")

    def handle(self, *args, **options):
        path = options["csv_path"]
        partner_id = options["partner_id"]
        dry_run = options["dry_run"]

        try:
            partner = PartnerPRO.objects.get(id=partner_id)
        except PartnerPRO.DoesNotExist:
            raise CommandError(f"PartnerPRO {partner_id} not found")

        created = 0
        updated = 0
        skipped = 0

        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required = {"isrc", "title"}
            if not required.issubset(reader.fieldnames or []):
                raise CommandError(f"CSV must include headers: {', '.join(sorted(required))}")

            for row in reader:
                isrc = (row.get("isrc") or "").strip()
                title = (row.get("title") or "").strip()
                work_title = (row.get("work_title") or "").strip() or None
                duration = row.get("duration_seconds")
                duration = int(duration) if (duration and str(duration).isdigit()) else None

                if not isrc and not title:
                    skipped += 1
                    continue

                if dry_run:
                    continue

                work = None
                if work_title:
                    work, _ = ExternalWork.objects.get_or_create(
                        origin_partner=partner,
                        title=work_title,
                        defaults={"iswc": None},
                    )

                obj, created_flag = ExternalRecording.objects.update_or_create(
                    origin_partner=partner,
                    isrc=isrc or None,
                    defaults={
                        "title": title or (work_title or "Unknown"),
                        "work": work,
                        "duration": duration,
                    },
                )
                if created_flag:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Imported CSV. created={created}, updated={updated}, skipped={skipped}, dry_run={dry_run}"
        ))

