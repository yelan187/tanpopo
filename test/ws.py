from rake_nltk import Rake

r = Rake()
r.extract_keywords_from_text("我都不知道你要干嘛")
print(r.get_ranked_phrases())