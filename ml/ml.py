import requests
import re
import nltk

from nltk.metrics import BigramAssocMeasures
from nltk.collocations import BigramCollocationFinder
from nltk import pos_tag
from nltk.tokenize import word_tokenize
from nltk.probability import FreqDist
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from rest_framework.views import APIView
from shops.models import Review
from rest_framework.response import Response
from rest_framework import permissions
from transformers import pipeline
from nltk.corpus import stopwords

nltk.download('punkt')
nltk.download('stopwords')
nltk.download('averaged_perceptron_tagger_eng')
nltk.download('punkt_tab')

# Load the model and tokenizer locally
tokenizer = AutoTokenizer.from_pretrained("facebook/bart-large-cnn")
model = AutoModelForSeq2SeqLM.from_pretrained("facebook/bart-large-cnn")


# Use the model in the pipeline
summarizer = pipeline("summarization", model=model, tokenizer=tokenizer)


def fetch_reviews(shop_id):
    url = f"http://localhost:8000/api/shops/{shop_id}/reviews/"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print("Failed to fetch reviews")
        return []


def preprocess_reviews(reviews):
    stop_words = set(stopwords.words('english'))
    cleaned_reviews = []
    for review in reviews:
        # Remove punctuation and lowercase
        text = re.sub(r'[^\w\s]', '', review.lower())
        tokens = word_tokenize(text)
        filtered_tokens = [word for word in tokens if word not in stop_words]
        cleaned_reviews.append(' '.join(filtered_tokens))
    return cleaned_reviews


def analyze_sentiment_with_keywords(reviews):
    try:
        sentiment_analyzer = pipeline("sentiment-analysis")
        stop_words = set(stopwords.words('english'))
        sentiments = []

        for review in reviews:
            # Analyze sentiment
            sentiment = sentiment_analyzer(review)[0]
            overall_sentiment = sentiment['label']
            score = sentiment['score']

            # Extract keywords and adjectives
            text = re.sub(r'[^\w\s]', '', review.lower())
            words = word_tokenize(text)
            filtered_words = [word for word in words if word not in stop_words]
            pos_tags = pos_tag(filtered_words)

            # Extract adjectives and filter out nouns
            adjectives = [word for word, tag in pos_tags if tag == 'JJ']
            adjectives = [adj for adj in adjectives if adj not in [
                word for word, tag in pos_tags if tag.startswith('NN')]]

            # Detect bigrams (e.g., "long wait")
            bigram_finder = BigramCollocationFinder.from_words(filtered_words)
            bigrams = bigram_finder.nbest(
                BigramAssocMeasures.likelihood_ratio, 5)  # Top 5 bigrams
            bigram_phrases = [' '.join(bigram) for bigram in bigrams]

            # Replace individual words with bigrams in adjectives
            combined_adjectives = []
            for adj in adjectives:
                for phrase in bigram_phrases:
                    if adj in phrase:
                        combined_adjectives.append(phrase)
                        break
                else:
                    combined_adjectives.append(adj)

            # Replace individual words with bigrams in keywords
            freq_dist = FreqDist(filtered_words)
            top_keywords = [word for word,
                            freq in freq_dist.most_common(3)]  # Top 3 keywords
            combined_keywords = []
            for keyword in top_keywords:
                for phrase in bigrams:
                    if keyword in phrase:
                        combined_keywords.append(' '.join(phrase))
                        break
                else:
                    combined_keywords.append(keyword)

            # Append sentiment, keywords, and adjectives
            sentiments.append({
                "review": review,
                "sentiment": overall_sentiment,
                "score": score,
                "keywords": combined_keywords,
                "adjectives": combined_adjectives
            })

        return sentiments
    except Exception as e:
        print(f"Error during sentiment analysis with keywords: {e}")
        return []


def enhance_summary_with_sentiment(sentiments):
    # Count sentiments
    positive_count = sum(
        1 for sentiment in sentiments if sentiment['sentiment'] == 'POSITIVE')
    negative_count = sum(
        1 for sentiment in sentiments if sentiment['sentiment'] == 'NEGATIVE')

    # Extract keywords and adjectives for each sentiment type
    positive_adjectives = [adj for sentiment in sentiments if sentiment['sentiment']
                           == 'POSITIVE' for adj in sentiment['adjectives']]
    negative_adjectives = [adj for sentiment in sentiments if sentiment['sentiment']
                           == 'NEGATIVE' for adj in sentiment['adjectives']]

    # Deduplicate and limit adjectives
    positive_adjectives = list(set(positive_adjectives))[
        :5]  # Limit to top 5 adjectives
    negative_adjectives = list(set(negative_adjectives))[:5]

    # Construct structured summaries
    summary = {
        "positive_count": positive_count,
        "negative_count": negative_count,
        "positive_adjectives": positive_adjectives,
        "negative_adjectives": negative_adjectives,
        "positive_summary": (
            f"Positive food reviews describe it as {', '.join(positive_adjectives)}."
            if positive_adjectives else "The food is not specifically described."
        ),
        "negative_summary": (
            f"Negative food reviews describe as {', '.join(negative_adjectives)}."
            if negative_adjectives else "The food is not specifically described."
        )
    }
    return summary


class ReviewSummaryView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, shop_id):
        try:
            # Fetch reviews for the shop
            reviews = Review.objects.filter(
                shop_id=shop_id).values('description')
            reviews_text = [review['description'] for review in reviews]

            # Block API if there are fewer than 5 reviews, reduce load on the server
            if len(reviews_text) < 5:
                return Response({"message": "Not enough reviews to generate a summary. At least 5 reviews are required."}, status=400)

            # Preprocess reviews
            cleaned_reviews = preprocess_reviews(reviews_text)

            # Analyze sentiment and extract keywords
            sentiments = analyze_sentiment_with_keywords(cleaned_reviews)

            # Enhance summary with sentiment overview
            sentiment_summary = enhance_summary_with_sentiment(sentiments)

            # Prepare the response
            return Response({
                "sentiments": sentiments,
                "summary": sentiment_summary
            })
        except Exception as e:
            print("error", e)
            return Response({"error": str(e)}, status=500)


detector = pipeline("text-classification",
                    model="Hello-SimpleAI/chatgpt-detector-roberta")


class ReviewFlagAIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, review_id):
        try:
            # Fetch the review text
            review = Review.objects.get(review_id=review_id)
            review_text = review.description

            # Detect if the review is AI-generated
            result = detector(review_text)
            print(result[0]['label'], result[0]['score'])

            return Response({
                "review_id": review_id,
                "label": result[0]['label'],
                'score': result[0]['score']
            })
        except Review.DoesNotExist:
            return Response({"error": "Review not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)
