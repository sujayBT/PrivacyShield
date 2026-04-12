**OCR** (Optical Character Recognition)

🔹 Definition



OCR (Optical Character Recognition) is a technology that converts printed, handwritten, or scanned text images into machine-readable digital text.



In simple words:

👉 It reads text from images or documents and turns it into editable text.



🔹 What OCR Does



OCR performs the following main tasks:



Text Detection

Identifies where text is located in an image or scanned document.

Character Recognition

Recognizes letters, numbers, and symbols.

Text Conversion

Converts the recognized characters into digital text (like Word, PDF, or TXT).

Data Extraction

Extracts useful information such as names, numbers, addresses, etc.

🔹 How OCR Works (Step-by-Step)

1\. Image Acquisition

Input is taken as:

Scanned document

Photo (from camera)

PDF file

2\. Pre-processing

Improves image quality:

Noise removal

Brightness/contrast adjustment

Skew correction

3\. Text Detection

Identifies regions that contain text.

4\. Character Segmentation

Breaks text into:

Lines → words → characters

5\. Feature Extraction

Extracts patterns like:

Edges

Shapes

Curves

6\. Character Recognition

Uses:

Pattern matching OR

Machine Learning / AI models

7\. Post-processing

Corrects errors using:

Dictionaries

Language models

🔹 Types of OCR

Simple OCR

Recognizes basic printed text

Intelligent OCR (IOCR)

Recognizes handwritten text

Optical Mark Recognition (OMR)

Detects marks (like exam answer sheets)



🔹 Applications of OCR

📚 Digitizing books and documents

🧾 Invoice and bill processing

🪪 ID card and passport scanning

🏦 Banking (cheque processing)

📱 Mobile apps (scan text from images)

🏢 Office automation

🔹 Advantages

Saves time (no manual typing)

Improves accuracy

Easy data storage and search

Automation of document processing

🔹 Limitations

Errors with:

Poor quality images

Complex fonts

Handwritten text (sometimes)

Requires good preprocessing







**Regex:**



👉 Regex (Regular Expression) is a pattern matching tool used to:



Find text

Validate text

Extract specific data



from a larger string.



🧠 Simple Idea



Think like this:



👉 OCR = gets the text from image

👉 Regex = filters or finds what you want from that text



✨ Example

Input text (from OCR):

Name: John Doe

Phone: 9876543210

Email: john@gmail.com

Using Regex:

Find phone number → \\d{10}

Find email → \[a-zA-Z0-9.\_%+-]+@\[a-zA-Z0-9.-]+\\.\[a-z]{2,}

🔧 Common Regex Patterns

Purpose	Regex

Digits only	\\d+

10-digit number	\\d{10}

Email	\[a-zA-Z0-9.\_%+-]+@\[a-zA-Z0-9.-]+\\.\[a-z]{2,}

Only alphabets	\[a-zA-Z]+

Remove spaces	\\s+

🔗 How It Connects to Your Project



👉 Your flow is probably:



OCR

Image → Text

Regex

Extract useful info from that text

📄 What You Can Write in Report



“After extracting text using OCR, Regular Expressions (Regex) are used to identify and extract specific patterns such as phone numbers, emails, and important fields.”



⚡ Simple Real-Life Example



👉 Aadhaar / ID card project:



OCR → gets all text

Regex → extracts:

Name

DOB

ID number



If you want, send your program code or idea — I’ll give you exact regex patterns for your project 🔥







WEEK 1 – REQUIREMENT ANALYSIS (HOW YOU SHOULD WORK)



This phase = understand problem deeply + define system clearly



🔍 1. Problem Understanding (DO THIS FIRST)



You must clearly understand:



👉 What is the real problem?



Your project problem:

People share screenshots \& PDFs

They contain:

phone numbers

emails

UPI IDs

Users don’t realize risk ❌

Result:

identity theft

fraud

privacy leak

🧠 Your understanding (important)



You should be able to explain:



👉 “This system helps users know how risky their shared content is before sharing.”



🔎 2. Study Existing Systems (Research part)



From your PDF :



Existing tools:



OCR tools → only extract text ❌

Antivirus → no privacy detection ❌

Security tools → not for screenshots ❌

Conclusion (VERY IMPORTANT)



👉 No tool combines:



OCR + Regex + Image classification + Scoring



💥 This is your research gap



🎯 3. Define Requirements



Now you define what system must do.



✅ Functional Requirements (what system DOES)



You should list like this:



Upload image or PDF

Extract text using OCR

Detect sensitive data (phone, email, UPI)

Calculate privacy score

Show risk level

Display result in UI

⚙️ Non-Functional Requirements (how system behaves)

Fast processing

High accuracy

Easy to use

Works offline

Secure data handling

📌 4. Define Scope



You must clearly say:



Included:

OCR detection

PDF scanning

scoring system

GUI

Not included (for now):

cloud processing

real-time monitoring

mobile app

🧭 5. Identify Users



Who will use your system?



students

social media users

small businesses

📊 6. Expected Output



What system gives:



extracted text

detected sensitive items

privacy score (0–100)

risk level (Low/Medium/High)

🔬 RESEARCH SOURCES (You can write in report)
🧠 1. OCR (Text Extraction)

You can cite:

Smith, R. (2007). An Overview of the Tesseract OCR Engine. 
Proceedings of the Ninth International Conference on Document Analysis and Recognition (ICDAR).

👉 Used for:

explaining OCR
why Tesseract is used
🔍 2. Regex & Pattern Detection
Friedl, J. E. F. (2006). Mastering Regular Expressions. O'Reilly Media.

👉 Used for:

detecting phone numbers, emails, etc.
🔐 3. Privacy & Data Exposure
Solove, D. J. (2006). A Taxonomy of Privacy. University of Pennsylvania Law Review.

👉 Used for:

explaining privacy risks
data exposure problems
🛡️ 4. Cybersecurity Risks
Stallings, W. (2018). Effective Cybersecurity: A Guide to Using Best Practices.
Pearson Education.

👉 Used for:

fraud, identity theft explanation
📊 5. Software Engineering Model
Pressman, R. S. (2010). Software Engineering: A Practitioner’s Approach.
McGraw-Hill.

👉 Used for:

requirement analysis
SDLC model
🧠 6. Image Classification (future module)
Krizhevsky, A., Sutskever, I., & Hinton, G. E. (2012).
ImageNet Classification with Deep Convolutional Neural Networks.
🧾 HOW TO USE THESE IN YOUR REPORT

At end of Week 1, add:

📌 References section
Writing

References:

[1] R. Smith, "An Overview of the Tesseract OCR Engine," ICDAR, 2007.
[2] J. Friedl, "Mastering Regular Expressions," O'Reilly, 2006.
[3] D. Solove, "A Taxonomy of Privacy," University of Pennsylvania Law Review, 2006.
[4] W. Stallings, "Effective Cybersecurity," Pearson, 2018.
[5] R. Pressman, "Software Engineering: A Practitioner’s Approach," McGraw-Hill, 2010.

