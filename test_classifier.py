from image_classifier import is_sensitive_image

img_path = "sample.png"

flag, results = is_sensitive_image(img_path)

print("\n--- RESULT ---")
print("Sensitive:", flag)

print("\nPredictions:")
for r in results:
    print(r)