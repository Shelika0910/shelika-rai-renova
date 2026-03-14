"""
Management command to populate the database with curated wellness resources,
motivational videos, and guided exercises for each mental health category.

Usage:
    python manage.py seed_resources
    python manage.py seed_resources --clear   # wipe existing data first
"""

from django.core.management.base import BaseCommand
from accounts.models import Resource, GuidedExercise


class Command(BaseCommand):
    help = "Seed the database with curated motivational videos, guided exercises, and relaxation techniques."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Delete all existing resources before seeding.")

    def handle(self, *args, **options):
        if options["clear"]:
            Resource.objects.all().delete()
            GuidedExercise.objects.all().delete()
            self.stdout.write(self.style.WARNING("Cleared existing resources."))

        resources_created = 0
        exercises_created = 0

        # ── MOTIVATIONAL VIDEOS ─────────────────────────────────────────
        videos = [
            # Anxiety
            {
                "title": "How to Cope with Anxiety",
                "description": "Practical strategies to manage anxious thoughts and regain control of your daily life. Learn evidence-based techniques from mental health experts.",
                "category": "anxiety",
                "resource_type": "video",
                "video_url": "https://www.youtube.com/embed/WWloIAQpMcQ",
                "duration": "10 min",
                "is_featured": True,
                "order": 1,
            },
            {
                "title": "Overcoming Anxiety – Motivational Speech",
                "description": "An inspiring talk about transforming anxiety into strength and finding peace within yourself.",
                "category": "anxiety",
                "resource_type": "video",
                "video_url": "https://www.youtube.com/embed/ntfcfJ28eiU",
                "duration": "8 min",
                "order": 2,
            },
            {
                "title": "Understanding Anxiety and Panic Attacks",
                "description": "Dr. Harry Barry explains the neuroscience behind anxiety and panic, and how you can break the cycle.",
                "category": "anxiety",
                "resource_type": "video",
                "video_url": "https://www.youtube.com/embed/S3RgOafiB1A",
                "duration": "15 min",
                "order": 3,
            },
            # Depression
            {
                "title": "Depression: Not Just a Bad Day",
                "description": "Understanding the difference between sadness and clinical depression. A compassionate guide to recognizing depression and seeking help.",
                "category": "depression",
                "resource_type": "video",
                "video_url": "https://www.youtube.com/embed/z-IR48Mb3W0",
                "duration": "6 min",
                "is_featured": True,
                "order": 1,
            },
            {
                "title": "What is Depression? – Animated Guide",
                "description": "A clear, animated explanation of depression — what it feels like, what causes it, and how treatment works.",
                "category": "depression",
                "resource_type": "video",
                "video_url": "https://www.youtube.com/embed/XiCrniLQGYc",
                "duration": "5 min",
                "order": 2,
            },
            {
                "title": "Motivation When Depressed – Small Steps",
                "description": "How to find motivation when Depression makes everything feel impossible. Practical micro-actions that build momentum.",
                "category": "depression",
                "resource_type": "video",
                "video_url": "https://www.youtube.com/embed/MB5IX-np5fE",
                "duration": "12 min",
                "order": 3,
            },
            # Stress
            {
                "title": "How to Make Stress Your Friend",
                "description": "Kelly McGonigal's famous TED Talk on reframing stress as a positive force that can improve your health and performance.",
                "category": "stress",
                "resource_type": "video",
                "video_url": "https://www.youtube.com/embed/RcGyVTAoXEU",
                "duration": "15 min",
                "is_featured": True,
                "order": 1,
            },
            {
                "title": "Stress Management Techniques",
                "description": "Five proven stress management techniques you can practice anywhere, anytime to lower cortisol and feel calmer.",
                "category": "stress",
                "resource_type": "video",
                "video_url": "https://www.youtube.com/embed/15GaKTP0gFE",
                "duration": "10 min",
                "order": 2,
            },
            # PTSD
            {
                "title": "Understanding PTSD and Trauma",
                "description": "A compassionate overview of PTSD — what trauma does to the brain and how recovery is possible through evidence-based treatment.",
                "category": "ptsd",
                "resource_type": "video",
                "video_url": "https://www.youtube.com/embed/b_n9qegR7C4",
                "duration": "5 min",
                "is_featured": True,
                "order": 1,
            },
            {
                "title": "Healing from Trauma – The Path Forward",
                "description": "Psychiatrist Dr. Bessel van der Kolk explains how the body keeps the score and what we can do to heal.",
                "category": "ptsd",
                "resource_type": "video",
                "video_url": "https://www.youtube.com/embed/53RX2ESIqsM",
                "duration": "18 min",
                "order": 2,
            },
            # General Wellness
            {
                "title": "The Science of Well-Being",
                "description": "Research-backed insights into what truly makes us happy and how to build lasting positive habits.",
                "category": "general",
                "resource_type": "video",
                "video_url": "https://www.youtube.com/embed/ZizdB0TgAVM",
                "duration": "12 min",
                "is_featured": True,
                "order": 1,
            },
            {
                "title": "How to Be Happy – Positive Psychology",
                "description": "A practical guide to building happiness through gratitude, connection, and mindful living.",
                "category": "general",
                "resource_type": "video",
                "video_url": "https://www.youtube.com/embed/GXy__kBVq1M",
                "duration": "11 min",
                "order": 2,
            },
        ]

        # ── RELAXATION TECHNIQUES ────────────────────────────────────────
        relaxation = [
            {
                "title": "Progressive Muscle Relaxation",
                "description": "A step-by-step guide to releasing tension from every muscle group. Tense each area for 5 seconds, then relax for 30 seconds. Start from your toes and work up to your head. Best done lying down in a quiet space.",
                "category": "anxiety",
                "resource_type": "relaxation",
                "video_url": "https://www.youtube.com/embed/86HUcX8ZtAk",
                "duration": "15 min",
                "order": 10,
            },
            {
                "title": "Body Scan Meditation",
                "description": "Close your eyes and bring gentle awareness to each part of your body. Notice sensations without judgment. This practice helps reconnect mind and body, reducing stress and emotional tension.",
                "category": "stress",
                "resource_type": "relaxation",
                "video_url": "https://www.youtube.com/embed/QS2yDmWk0vs",
                "duration": "20 min",
                "order": 10,
            },
            {
                "title": "Guided Visualization – Safe Place",
                "description": "Create a vivid mental image of your personal safe place. Engage all five senses — see the colors, hear the sounds, feel the temperature. This technique is especially helpful for trauma recovery.",
                "category": "ptsd",
                "resource_type": "relaxation",
                "video_url": "https://www.youtube.com/embed/t1rRo6cgM_E",
                "duration": "12 min",
                "order": 10,
            },
            {
                "title": "Deep Breathing for Relaxation",
                "description": "Learn the 4-7-8 breathing technique: Inhale for 4 counts, hold for 7 counts, exhale for 8 counts. This activates your parasympathetic nervous system and induces calm within minutes.",
                "category": "general",
                "resource_type": "relaxation",
                "duration": "5 min",
                "order": 10,
            },
            {
                "title": "Positive Affirmation Meditation",
                "description": "A gentle meditation with positive affirmations to counter negative self-talk and build self-compassion. Repeat phrases like 'I am worthy of peace' and 'I choose to let go of worry.'",
                "category": "depression",
                "resource_type": "relaxation",
                "video_url": "https://www.youtube.com/embed/z0GtmPnqAd8",
                "duration": "10 min",
                "order": 10,
            },
        ]

        for data in videos + relaxation:
            _, created = Resource.objects.get_or_create(
                title=data["title"],
                defaults=data,
            )
            if created:
                resources_created += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {resources_created} resources."))