from django.core.management.base import BaseCommand

from classes.models import ClassSession, ClassType


class Command(BaseCommand):
    help = "Normalize existing demo class session and class type names for demo data."

    def handle(self, *args, **options):
        prefixes = ("Upcoming ", "Active ", "Completed ", "Cancelled ")
        session_updated_count = 0
        class_type_updated_count = 0

        for session in ClassSession.objects.filter(class_name__icontains=" Batch "):
            original_name = session.class_name
            normalized_name = original_name

            for prefix in prefixes:
                if normalized_name.startswith(prefix):
                    normalized_name = normalized_name[len(prefix):]
                    break

            normalized_name = normalized_name.replace("Weekend Recovery", "Recovery Swim")

            if normalized_name != original_name:
                session.class_name = normalized_name
                session.save(update_fields=["class_name"])
                session_updated_count += 1

        for class_type in ClassType.objects.filter(name="Demo Weekend Recovery"):
            class_type.name = "Demo Recovery Swim"
            class_type.save(update_fields=["name"])
            class_type_updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Normalized {session_updated_count} class session name(s) and {class_type_updated_count} class type name(s)."
            )
        )
