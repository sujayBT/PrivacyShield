import inspect
import backend.services.ai_detection as a
import backend.services.recommendations as r

fns = ['enrich_regex_findings','analyze_with_spacy','score_ai_findings']
for n in fns:
    if hasattr(a, n):
        print(f"ai_detection.{n}: {inspect.signature(getattr(a,n))}")
    else:
        print(f"ai_detection.{n}: NOT FOUND")

print()
for n in ['generate_recommendations']:
    if hasattr(r, n):
        print(f"recommendations.{n}: {inspect.signature(getattr(r,n))}")
