import unicodedata
import re

# Pre-compiled regex for markers performance optimization
_MARKERS = [
    r"\[字\]", r"\[再\]", r"\[初\]", r"\[解\]", r"\[二\]", r"\[単\]", r"\[選\]", r"\[多\]", r"\[s\]", r"\[ss\]", r"\[pv\]",
    r"\[映\]", r"\[画\]", r"\[料\]", r"\[教\]", r"\[候\]", r"\[公\]", r"\[表\]", r"\[別\]", r"\[契\]", r"\[編\]", r"\[勝\]",
    r"\[録\]", r"\[視\]", r"\[語\]", r"\[終\]", r"\[新\]", r"\[デ\]", r"\[無料\]",
    r"\(字\)", r"\(再\)", r"\(初\)", r"\(解\)", r"\(二\)", r"\(単\)", r"\(選\)", r"\(多\)", r"\(s\)", r"\(ss\)", r"\(pv\)",
    r"\(映\)", r"\(画\)", r"\(料\)", r"\(教\)", r"\(候\)", r"\(公\)", r"\(表\)", r"\(別\)", r"\(契\)", r"\(編\)", r"\(勝\)",
    r"\(録\)", r"\(視\)", r"\(語\)", r"\(終\)", r"\(新\)", r"\(デ\)", r"\(無料\)"
]
_MARKERS_RE = re.compile("|".join(_MARKERS))

def normalize_text(text: str) -> str:
    """
    データベース保存用の文字列正規化を行います。
    全角英数字を半角に変換（NFKC）しますが、大文字小文字の変換や空白の除去は行いません。
    """
    if not text:
        return text
    return unicodedata.normalize('NFKC', text)

def normalize_string(s: str) -> str:
    """
    自動予約のマッチング検索用の高度な文字列正規化を行います。
    全角半角の統一（NFKC）、小文字化、記号の統一、特定の括弧表記の除去、空白の除去などを行い
    表記揺れを吸収します。
    """
    if not s: return ""
    # NFKC handles full-width/half-width conversion to a standard form
    s = unicodedata.normalize('NFKC', s).lower().strip()
    
    # Unify different bracket types used in EPG
    s = s.replace("【", "[").replace("】", "]")
    s = s.replace("≪", "[").replace("≫", "]")
    s = s.replace("《", "[").replace("》", "]")
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace("［", "[").replace("］", "]")
    s = s.replace("〔", "[").replace("〕", "]")

    # Remove common EPG markers for stable comparison using pre-compiled regex (High Performance)
    s = _MARKERS_RE.sub("", s)
    
    # Remove content after certain separators if they likely contain cast/staff info,
    # but PRESERVE episode info like #123, 第1回, or 「SubTitle」.
    separators = ["／", " - ", " / "] 
    for sep in separators:
        if sep in s:
            s = s.split(sep)[0]
            
    # Remove all whitespace for final comparison robustness
    s = "".join(s.split())
            
    return s.strip()
