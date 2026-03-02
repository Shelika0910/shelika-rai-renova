"""
Management command to populate assessment questions.
Run: python manage.py populate_assessment
"""
from django.core.management.base import BaseCommand
from accounts.models import AssessmentQuestion, AssessmentChoice

# Answer choices: (text, weight 0-4)
ANSWER_CHOICES = [
    ("Never", 0),
    ("Rarely", 1),
    ("Sometimes", 2),
    ("Often", 3),
    ("Always", 4),
]

QUESTIONS = [
    # Stress
    ("I feel overwhelmed by my daily responsibilities.", "stress"),
    ("I have difficulty relaxing even when I have free time.", "stress"),
    ("I experience physical symptoms (headaches, tension) when stressed.", "stress"),
    ("I struggle to maintain work-life balance.", "stress"),
    # Anxiety
    ("I worry about things that might go wrong.", "anxiety"),
    ("I feel restless or on edge.", "anxiety"),
    ("I avoid situations that make me anxious.", "anxiety"),
    ("I experience panic or sudden fear without obvious cause.", "anxiety"),
    ("I find it hard to stop worrying once I start.", "anxiety"),
    # Sleep
    ("I have trouble falling asleep or staying asleep.", "sleep_issues"),
    ("I wake up feeling tired despite sleeping.", "sleep_issues"),
    ("My sleep schedule is inconsistent.", "sleep_issues"),
    # Depression
    ("I feel sad or down most days.", "depression"),
    ("I have lost interest in activities I used to enjoy.", "depression"),
    ("I feel hopeless about the future.", "depression"),
    ("I have difficulty concentrating or making decisions.", "depression"),
    # PTSD
    ("I have intrusive thoughts or memories of past trauma.", "ptsd"),
    ("I feel emotionally numb or detached.", "ptsd"),
    ("I am easily startled or hypervigilant.", "ptsd"),
    # Relationship
    ("I have difficulty communicating with people close to me.", "relationship"),
    ("I feel isolated or disconnected from others.", "relationship"),
    ("I experience conflict in my relationships.", "relationship"),
]


class Command(BaseCommand):
    help = "Populate assessment questions and choices"

    def handle(self, *args, **options):
        if AssessmentQuestion.objects.exists():
            self.stdout.write(self.style.WARNING("Assessment questions already exist. Skipping."))
            return

        for order, (text, category) in enumerate(QUESTIONS, 1):
            q = AssessmentQuestion.objects.create(
                text=text,
                category=category,
                order=order,
            )
            for choice_text, weight in ANSWER_CHOICES:
                AssessmentChoice.objects.create(
                    question=q,
                    text=choice_text,
                    weight=weight,
                )
        self.stdout.write(self.style.SUCCESS(f"Created {len(QUESTIONS)} questions with choices."))
