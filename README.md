# 🎴 PokeCollect OCR
An AI-powered Pokemon TCG card scanner that uses computer vision to identify cards from photos with 100% precision validation. Built with Python, OpenAI's GPT-4 Vision, and the Pokemon TCG API, this project automatically recognizes Pokemon cards and adds them to your collection. I built this side project for learning purposes and to solve a real problem – manually cataloging a Pokemon card collection is tedious and error-prone.

## 📦 Technologies
- Python & FastAPI
- OpenAI GPT-4 Vision API
- Pokemon TCG API
- PIL (Pillow) for image processing
- RapidFuzz for fuzzy matching
- Supabase (optional collection storage)
- Docker

## 🦄 Features
Here's what you can do with PokeCollect OCR:

**AI-Powered Card Recognition**: Upload a photo of any Pokemon card and the AI extracts the card name, number, set information, and rarity using GPT-4 Vision OCR.

**Strict Validation System**: Four-level validation ensures only correct matches are returned – no ambiguous results. Better to return nothing than return the wrong card.

**Fuzzy Matching Intelligence**: Handles typos and variations in card names gracefully. If OCR reads "Pikachuu" instead of "Pikachu", the system still finds the right card.

**Confidence Scoring**: Each match gets a confidence score (0-100%). Only matches above 70% are shown, with badges indicating if manual verification is recommended.

**Batch Upload Support**: Scan multiple cards at once. Perfect for quickly digitizing your entire collection or newly acquired cards.

**Interactive Web Interface**: Drag-and-drop interface with real-time feedback. Upload photos, see results instantly, and add cards to your collection with one click.

**Debug Information**: When a card isn't found, the system shows exactly what it extracted from the image and why no match was made. This transparency helps improve photo quality.

**Collection Management**: Optional Supabase integration lets you build and track your digital card collection with automatic price tracking.

## 🎯 How It Works
1. **Upload**: Drag a card photo into the web interface
2. **OCR Extraction**: GPT-4 Vision reads the card name, number, set, and rarity
3. **Smart Matching**: System tries multiple query strategies to find the card in the TCG database
4. **Strict Validation**: Four validation rules ensure the match is correct
5. **Result**: You see the matched card with confidence score, price, and image
6. **Collection**: Optionally add the card to your digital collection

## 👩🏽‍🍳 The Process
I started this project because I'd collected Pokemon cards since childhood, and cataloging hundreds of cards manually was exhausting. I wanted to just take photos and have a system figure out what cards they were.

The first challenge was OCR accuracy. Pokemon cards have stylized fonts, foil textures, and varying lighting conditions. I experimented with traditional OCR libraries (Tesseract, EasyOCR) but results were inconsistent. GPT-4 Vision changed everything – its ability to understand context made card reading dramatically more accurate.

Next was the matching problem. Even with perfect OCR, finding the right card in a database of 20,000+ cards is tricky. A card might be "Pik achu" due to OCR errors, or the set name might be abbreviated. I built a progressive matching system that tries exact matches first, then falls back to fuzzy matching, finally trying number-only searches.

The validation system evolved after I got tired of false positives. Early versions would confidently return the wrong card. I implemented strict rules: exact card number match required, name similarity must be 85%+, and if two candidates are too close in score, reject both for being ambiguous.

Building the web interface taught me about user feedback. When scanning fails, users need to know why. Is the photo blurry? Is the card too obscure? I added detailed debug output that explains what went wrong and suggests improvements.

Integration with Supabase for collection management was optional but valuable. Users can build a digital collection that syncs across devices, track card values over time, and quickly see which cards they're missing from a set.

Performance optimization involved image preprocessing (resizing, orientation correction) and caching TCG API results to avoid redundant requests. The goal was sub-5-second scans without overwhelming external APIs.

## 📚 What I Learned
During this project, I've picked up important skills and a deeper understanding of computer vision, API design, and data matching algorithms.

### 🤖 AI & Computer Vision
**GPT-4 Vision API**: I learned how to craft effective prompts for vision models, handle base64 image encoding, and work within token limits. The right prompt made the difference between 60% and 95% accuracy.

**OCR Challenges**: Dealing with real-world images taught me about preprocessing – handling rotations, reflections, lighting variations, and image quality issues that affect recognition accuracy.

### 🔍 Data Matching & Algorithms
**Fuzzy Matching**: Implementing smart text similarity taught me about edit distance algorithms (Levenshtein), token-based matching, and when to use which technique for best results.

**Progressive Fallbacks**: Building a multi-level matching system taught me about graceful degradation – start with strict requirements, progressively relax them, but never compromise on final validation.

**Ambiguity Detection**: Learning to identify when results are uncertain taught me about confidence scoring, statistical significance, and how to communicate uncertainty to users.

### 🎯 Validation & Precision
**Rule-Based Validation**: I learned that AI output needs strict validation. Four simple rules (minimum score, exact number match, name similarity, uniqueness) transformed an unreliable system into a dependable one.

**False Positive vs False Negative Trade-offs**: Deciding to reject ambiguous matches taught me about precision vs recall – sometimes returning nothing is better than returning something wrong.

### 🌐 API Design
**RESTful Endpoints**: Building a FastAPI service taught me about proper HTTP status codes, error handling, request validation, and how to design intuitive API interfaces.

**External API Integration**: Working with the Pokemon TCG API taught me about rate limiting, caching strategies, and how to be a responsible API consumer.

### 📈 Overall Growth
This project taught me that accuracy matters more than feature count. A simple tool that works reliably beats a complex tool that sometimes fails.

Working with AI made me appreciate the importance of validation. AI is powerful but not infallible – the real engineering is in verifying outputs and handling edge cases.

Most importantly, I learned about user-centric error messaging. When something fails, tell the user exactly why and how to fix it. Transparency builds trust, even when the system isn't perfect.

## 💭 How can it be improved?
- Add support for Japanese and other language cards
- Implement card condition grading (Mint, Near Mint, etc.)
- Add bulk pricing estimates for collections
- Create mobile app for on-the-go scanning
- Implement set completion tracking and wishlists
- Add trading features (match users who have cards you need)
- Support for other TCGs (Magic, Yu-Gi-Oh)
- Improve OCR with custom fine-tuned models
- Add barcode scanning for sealed products
- Implement duplicate detection in collections

## 🚦 Running the Project
To run the project in your local environment, follow these steps:

1. Clone the repository:
   ```bash
   git clone https://github.com/Shipwithsimo/-pokecollect-ocr.git
   cd -pokecollect-ocr/ocr-service
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   ```

4. Run the development server:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

5. Open http://localhost:8000 in your browser to access the web interface

## 🎥 Preview
A clean web interface with a large drag-and-drop zone for card photos. After uploading, you see the recognized card with its image, name, set, number, rarity, and current market price. A confidence badge (✓ VERIFIED or ⚠ VERIFY) indicates match reliability. If no match is found, detailed debug information shows what the AI extracted and why validation failed.
