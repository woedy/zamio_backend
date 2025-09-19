import csv
from typing import Optional

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Export your Tracks into a CSV with headers "
        "isrc,title,work_title,duration_seconds for partner import."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            dest="out_path",
            default="sample_partner_import.csv",
            help="Output CSV path (default: sample_partner_import.csv)",
        )
        parser.add_argument(
            "--only-isrc",
            action="store_true",
            default=True,
            help="Only include tracks that have an ISRC (default: True)",
        )
        parser.add_argument(
            "--include-no-isrc",
            action="store_true",
            help="Include tracks without ISRC (overrides --only-isrc)",
        )
        parser.add_argument(
            "--publisher-id",
            type=int,
            dest="publisher_id",
            help="Filter by PublisherProfile id (optional)",
        )
        parser.add_argument(
            "--artist-id",
            type=int,
            dest="artist_id",
            help="Filter by Artist id (optional)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            dest="limit",
            help="Limit number of exported rows (optional)",
        )

    def handle(self, *args, **options):
        from artists.models import Track  # Import here to avoid circulars at load time

        out_path: str = options["out_path"]
        only_isrc: bool = options.get("only_isrc", True)
        include_no_isrc: bool = options.get("include_no_isrc", False)
        publisher_id: Optional[int] = options.get("publisher_id")
        artist_id: Optional[int] = options.get("artist_id")
        limit: Optional[int] = options.get("limit")

        qs = Track.objects.all().select_related("artist", "publisher")

        if publisher_id:
            qs = qs.filter(publisher_id=publisher_id)
        if artist_id:
            qs = qs.filter(artist_id=artist_id)

        if not include_no_isrc and only_isrc:
            qs = qs.exclude(isrc_code__isnull=True).exclude(isrc_code__exact="")

        if limit:
            qs = qs[:limit]

        count = qs.count()
        if count == 0:
            self.stdout.write(self.style.WARNING("No tracks found matching filters; CSV will still be created with headers."))

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "isrc",
                    "title",
                    "work_title",
                    "duration_seconds",
                ],
            )
            writer.writeheader()

            for t in qs.iterator():
                # Map Track fields to expected import columns
                isrc = (t.isrc_code or "").strip() if t.isrc_code else ""
                title = (t.title or "").strip()
                work_title = title  # In absence of a Work model, reuse track title

                duration_seconds = None
                if t.duration:
                    try:
                        duration_seconds = int(t.duration.total_seconds())
                    except Exception:
                        duration_seconds = None

                writer.writerow(
                    {
                        "isrc": isrc,
                        "title": title,
                        "work_title": work_title,
                        "duration_seconds": duration_seconds if duration_seconds is not None else "",
                    }
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Exported {count} track(s) to {out_path} with headers: isrc,title,work_title,duration_seconds"
            )
        )

