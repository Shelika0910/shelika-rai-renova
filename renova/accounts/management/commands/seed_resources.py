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

        # ── GUIDED EXERCISES ─────────────────────────────────────────────
        exercises = [
            # Anxiety
            {
                "title": "4-7-8 Breathing Technique",
                "description": "A powerful calming exercise. Breathe in for 4 seconds, hold for 7 seconds, and exhale slowly for 8 seconds. This activates your body's relaxation response and is perfect for moments of acute anxiety.",
                "category": "anxiety",
                "exercise_type": "breathing",
                "difficulty": "beginner",
                "duration_minutes": 5,
                "icon": "🌬️",
                "steps": [
                    "Find a comfortable seated position and close your eyes.",
                    "Place the tip of your tongue behind your upper front teeth.",
                    "Exhale completely through your mouth, making a gentle whoosh sound.",
                    "Close your mouth and inhale quietly through your nose for 4 seconds.",
                    "Hold your breath gently for 7 seconds.",
                    "Exhale completely through your mouth for 8 seconds with a whoosh.",
                    "This completes one breath cycle. Repeat for 4 full cycles.",
                    "Gradually increase to 8 cycles as you become comfortable.",
                    "Open your eyes slowly and notice how your body feels.",
                ],
            },
            {
                "title": "Grounding: 5-4-3-2-1 Senses",
                "description": "A grounding technique that brings you into the present moment by engaging all five senses. Especially effective during anxiety attacks or dissociation.",
                "category": "anxiety",
                "exercise_type": "grounding",
                "difficulty": "beginner",
                "duration_minutes": 5,
                "icon": "🌍",
                "steps": [
                    "Pause and take three slow, deep breaths.",
                    "Name 5 things you can SEE around you (e.g., a lamp, a book, your hands).",
                    "Name 4 things you can TOUCH (e.g., the fabric of your shirt, the chair beneath you).",
                    "Name 3 things you can HEAR (e.g., traffic, a fan, birdsong).",
                    "Name 2 things you can SMELL (e.g., coffee, fresh air).",
                    "Name 1 thing you can TASTE (e.g., toothpaste, water).",
                    "Take three more slow breaths and notice how much calmer you feel.",
                ],
            },
            {
                "title": "Anxiety Thought Journal",
                "description": "Write down anxious thoughts and challenge them with evidence-based questions. This cognitive restructuring exercise helps you see situations more clearly.",
                "category": "anxiety",
                "exercise_type": "journaling",
                "difficulty": "intermediate",
                "duration_minutes": 15,
                "icon": "📝",
                "steps": [
                    "Write down the anxious thought that's bothering you right now.",
                    "Rate your anxiety level from 1-10.",
                    "Ask: 'What is the evidence FOR this thought being true?'",
                    "Ask: 'What is the evidence AGAINST this thought being true?'",
                    "Ask: 'What would I tell a friend who had this thought?'",
                    "Write a more balanced, realistic version of the thought.",
                    "Rate your anxiety level again from 1-10. Notice any change.",
                ],
            },
            # Depression
            {
                "title": "Morning Gratitude Practice",
                "description": "Start your day by acknowledging three things you're grateful for. This simple practice rewires your brain to notice positive experiences and builds resilience against depressive thinking.",
                "category": "depression",
                "exercise_type": "journaling",
                "difficulty": "beginner",
                "duration_minutes": 10,
                "icon": "☀️",
                "steps": [
                    "Before checking your phone, sit up and take 5 deep breaths.",
                    "Write down 3 things you're grateful for today — they can be small.",
                    "For each one, write WHY it matters to you (1-2 sentences).",
                    "Write one thing you're looking forward to today.",
                    "Write one kind thing you'll do for yourself today.",
                    "Read your list out loud once, slowly.",
                    "Close your journal and notice any shift in your mood.",
                ],
            },
            {
                "title": "Gentle Movement Meditation",
                "description": "A combination of slow movement and breath awareness designed to gently lift energy levels when depression makes everything feel heavy.",
                "category": "depression",
                "exercise_type": "mindfulness",
                "difficulty": "beginner",
                "duration_minutes": 10,
                "icon": "🧘",
                "steps": [
                    "Stand in a comfortable position. Let your arms hang loose.",
                    "Take 3 slow breaths. Inhale through nose, exhale through mouth.",
                    "Slowly raise your arms out to the sides and up overhead. Breathe in.",
                    "Lower them slowly back down. Breathe out.",
                    "Repeat this 5 times, moving as slowly as feels comfortable.",
                    "Place your hands on your heart. Feel the warmth and rhythm.",
                    "Gently roll your shoulders backward 5 times, then forward 5 times.",
                    "Shake your hands vigorously for 10 seconds — let go of tension.",
                    "Stand still. Take 3 final breaths and notice how your body feels now.",
                ],
            },
            # Stress
            {
                "title": "Box Breathing for Stress",
                "description": "Used by Navy SEALs and first responders. This technique calms the nervous system in minutes. Equal-length inhale, hold, exhale, and hold creates a 'box' pattern.",
                "category": "stress",
                "exercise_type": "breathing",
                "difficulty": "beginner",
                "duration_minutes": 5,
                "icon": "📦",
                "steps": [
                    "Sit upright in a comfortable position with feet flat on the floor.",
                    "Close your eyes or soften your gaze.",
                    "Inhale slowly through your nose for 4 seconds.",
                    "Hold your breath for 4 seconds — stay relaxed.",
                    "Exhale slowly through your mouth for 4 seconds.",
                    "Hold your breath (empty lungs) for 4 seconds.",
                    "Repeat this 'box' pattern for 4-6 rounds.",
                    "Gradually increase to 6-second intervals as you improve.",
                    "Open your eyes. You should feel noticeably calmer.",
                ],
            },
            {
                "title": "Progressive Muscle Relaxation",
                "description": "Systematically tense and release each muscle group to melt away physical stress. This technique teaches your body the difference between tension and relaxation.",
                "category": "stress",
                "exercise_type": "relaxation",
                "difficulty": "beginner",
                "duration_minutes": 15,
                "icon": "💪",
                "steps": [
                    "Lie down or sit comfortably. Close your eyes. Take 3 deep breaths.",
                    "FEET: Curl your toes tightly for 5 seconds. Release. Feel the difference.",
                    "CALVES: Flex your calves by pointing toes up. Hold 5 sec. Release.",
                    "THIGHS: Squeeze your thigh muscles tightly. Hold 5 sec. Release.",
                    "ABDOMEN: Tighten your stomach muscles. Hold 5 sec. Release.",
                    "HANDS: Make tight fists. Hold 5 sec. Release and spread fingers wide.",
                    "ARMS: Flex your biceps tightly. Hold 5 sec. Release.",
                    "SHOULDERS: Raise shoulders to your ears. Hold 5 sec. Drop them down.",
                    "FACE: Scrunch your face tightly. Hold 5 sec. Release completely.",
                    "Take 5 deep breaths. Notice how relaxed your entire body feels now.",
                ],
            },
            # PTSD
            {
                "title": "Safe Place Visualization",
                "description": "Create a detailed mental image of a place where you feel completely safe. This technique builds an internal resource you can access whenever you feel triggered.",
                "category": "ptsd",
                "exercise_type": "meditation",
                "difficulty": "intermediate",
                "duration_minutes": 10,
                "icon": "🏠",
                "steps": [
                    "Sit comfortably and close your eyes. Take 5 slow, deep breaths.",
                    "Think of a place — real or imagined — where you feel completely safe.",
                    "See it clearly in your mind. Notice the colors, light, and shapes.",
                    "What sounds are in your safe place? Birds, waves, silence, soft music?",
                    "What can you feel? Warmth, a cool breeze, soft ground beneath you?",
                    "What do you smell? Flowers, fresh air, something cooking?",
                    "Place your hand over your heart. Say: 'I am safe right now.'",
                    "Stay in your safe place for 2-3 minutes, breathing slowly.",
                    "When ready, wiggle your fingers and toes and open your eyes gently.",
                    "Remember: you can return to this place whenever you need to.",
                ],
            },
            {
                "title": "Butterfly Hug – Self-Soothing",
                "description": "A bilateral stimulation technique developed for trauma survivors. Cross your arms over your chest and alternate tapping your shoulders. Simple yet profoundly calming.",
                "category": "ptsd",
                "exercise_type": "grounding",
                "difficulty": "beginner",
                "duration_minutes": 5,
                "icon": "🦋",
                "steps": [
                    "Sit or stand comfortably. Close your eyes if that feels safe.",
                    "Cross your arms over your chest so each hand rests on the opposite shoulder.",
                    "Begin alternating taps — left hand taps right shoulder, then right hand taps left.",
                    "Tap at a slow, comfortable rhythm (about 1 tap per second on each side).",
                    "As you tap, breathe slowly and think of something calm or say 'I am safe.'",
                    "Continue for 2-3 minutes.",
                    "Pause. Notice how your body feels — any areas of tension or release.",
                    "If you feel calmer, continue for another round. If not, that's okay too.",
                ],
            },
            # General Wellness
            {
                "title": "Mindful Morning Check-In",
                "description": "A 5-minute mindfulness practice to start your day with intention. Check in with your body, emotions, and thoughts without judgment.",
                "category": "general",
                "exercise_type": "mindfulness",
                "difficulty": "beginner",
                "duration_minutes": 5,
                "icon": "🌅",
                "steps": [
                    "Sit comfortably and take 3 deep breaths.",
                    "BODY: Scan from head to toe. Where do you feel tension? Comfort?",
                    "EMOTIONS: Name your current emotion without judging it. Just notice.",
                    "THOUGHTS: What's on your mind today? Acknowledge it, then let it pass.",
                    "INTENTION: Choose one word for today (e.g., 'calm', 'focus', 'kind').",
                    "Take 3 more breaths with your chosen word in mind.",
                    "Open your eyes. Carry your intention with you through the day.",
                ],
            },
            {
                "title": "Loving-Kindness Meditation",
                "description": "Cultivate compassion for yourself and others through this ancient meditation practice. Repeat phrases of kindness directed at yourself, loved ones, and eventually all beings.",
                "category": "general",
                "exercise_type": "meditation",
                "difficulty": "intermediate",
                "duration_minutes": 10,
                "icon": "💚",
                "steps": [
                    "Sit comfortably and close your eyes. Take 5 deep breaths.",
                    "Place your hand on your heart. Feel its warmth.",
                    "Direct kindness to YOURSELF: 'May I be happy. May I be healthy. May I be safe. May I live with ease.'",
                    "Think of someone you LOVE. Send them the same wishes: 'May you be happy...'",
                    "Think of a NEUTRAL person (a barista, neighbor). Send them the wishes.",
                    "Think of someone DIFFICULT. Try to send them the wishes with compassion.",
                    "Expand your circle to ALL BEINGS everywhere: 'May all beings be happy...'",
                    "Sit in the feeling of warmth and connection for 1 minute.",
                    "Open your eyes gently. Carry this compassion with you today.",
                ],
            },
        ]

        for data in exercises:
            _, created = GuidedExercise.objects.get_or_create(
                title=data["title"],
                defaults=data,
            )
            if created:
                exercises_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done! Created {resources_created} resources and {exercises_created} guided exercises."
        ))
