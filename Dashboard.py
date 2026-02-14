import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import plotly.express as px
from datetime import datetime, timedelta
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import os
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline
import pytz
import warnings
warnings.filterwarnings('ignore')

# Configuration de la page
st.set_page_config(
    page_title="Tracker Bourse Israël - TASE",
    page_icon="🇮🇱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration du fuseau horaire
USER_TIMEZONE = pytz.timezone('Europe/Paris')  # UTC+2 (heure d'été)
ISRAEL_TIMEZONE = pytz.timezone('Asia/Jerusalem')  # UTC+2/UTC+3 (Idt)
US_TIMEZONE = pytz.timezone('America/New_York')

# Style CSS personnalisé
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #0038b8;
        text-align: center;
        margin-bottom: 2rem;
        font-family: 'Arial Hebrew', 'David', sans-serif;
    }
    .stock-price {
        font-size: 2.5rem;
        font-weight: bold;
        color: #0038b8;
        text-align: center;
    }
    .stock-change-positive {
        color: #00cc96;
        font-size: 1.2rem;
        font-weight: bold;
    }
    .stock-change-negative {
        color: #ef553b;
        font-size: 1.2rem;
        font-weight: bold;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .alert-box {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .alert-success {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .alert-warning {
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        color: #856404;
    }
    .portfolio-table {
        font-size: 0.9rem;
    }
    .stButton>button {
        width: 100%;
    }
    .timezone-badge {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
        padding: 0.5rem 1rem;
        margin: 1rem 0;
        font-size: 0.9rem;
    }
    .israel-market-note {
        background-color: #f0f5ff;
        border-left: 4px solid #0038b8;
        padding: 1rem;
        margin: 1rem 0;
    }
    .hebrew-text {
        font-family: 'Arial Hebrew', 'David', sans-serif;
        direction: rtl;
    }
</style>
""", unsafe_allow_html=True)

# Initialisation des variables de session
if 'price_alerts' not in st.session_state:
    st.session_state.price_alerts = []

if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}

if 'watchlist' not in st.session_state:
    st.session_state.watchlist = [
        'TEVA',           # Teva Pharmaceutical Industries (TA100, aussi listé US)
        'AZRG.TA',        # Azrieli Group
        'BEZQ.TA',        # Bezeq
        'LUMI.TA',        # Bank Leumi
        'POLI.TA',        # Bank Hapoalim
        'ICL.TA',         # ICL Group
        'NICE',           # Nice Systems (TA100 & NASDAQ)
        'ELAL.TA',        # El Al Airlines
        'ENOG.TA',        # Energix
        'KSML.TA'         # Kamada
    ]

if 'notifications' not in st.session_state:
    st.session_state.notifications = []

if 'email_config' not in st.session_state:
    st.session_state.email_config = {
        'enabled': False,
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'email': '',
        'password': ''
    }

# Mapping des suffixes TASE
TASE_EXCHANGES = {
    '.TA': 'Tel Aviv',
    '': 'US Listed/Global'
}

# Jours fériés israéliens (dates variables, liste partielle)
ISRAELI_HOLIDAYS_2024 = [
    '2024-03-24',  # Pourim
    '2024-04-22',  # Pessah (1er jour)
    '2024-04-23',  # Pessah (2ème jour)
    '2024-04-28',  # Pessah (7ème jour)
    '2024-04-29',  # Pessah (8ème jour)
    '2024-05-13',  # Yom Ha'atzmaut
    '2024-06-11',  # Shavouot
    '2024-10-03',  # Roch Hachana
    '2024-10-04',  # Roch Hachana
    '2024-10-13',  # Yom Kippour
    '2024-10-18',  # Souccot
    '2024-10-19',  # Souccot
    '2024-10-25',  # Sim'hat Torah
]

# Titre principal
st.markdown("<h1 class='main-header'>🇮🇱 Tracker Bourse Israël - TASE en Temps Réel</h1>", unsafe_allow_html=True)

# Bannière de fuseau horaire
current_time_utc2 = datetime.now(USER_TIMEZONE)
current_time_israel = datetime.now(ISRAEL_TIMEZONE)
current_time_us = datetime.now(US_TIMEZONE)

st.markdown(f"""
<div class='timezone-badge'>
    <b>🕐 Fuseaux horaires :</b><br>
    🇪🇺 Votre heure : {current_time_utc2.strftime('%H:%M:%S')} (UTC+2)<br>
    🇮🇱 Heure Israël : {current_time_israel.strftime('%H:%M:%S')} (UTC+2/UTC+3)<br>
    🇺🇸 Heure NY : {current_time_us.strftime('%H:%M:%S')} (UTC-4/UTC-5)<br>
    📍 Décalage : {int((current_time_israel.utcoffset().total_seconds() - current_time_utc2.utcoffset().total_seconds())/3600)}h avec Israël
</div>
""", unsafe_allow_html=True)

# Note sur les marchés israéliens
st.markdown("""
<div class='israel-market-note'>
    <b>🇮🇱 Bourse de Tel Aviv (TASE) :</b><br>
    - Actions locales: suffixe .TA (ex: LUMI.TA, BEZQ.TA)<br>
    - Double cotation: symboles US (TEVA, NICE, ICL)<br>
    - Horaires trading: Dimanche-Jeudi 09:45-16:25 (heure Israël)<br>
    - Fermé le vendredi, samedi et jours fériés juifs
</div>
""", unsafe_allow_html=True)

# Sidebar pour la navigation
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/israel.png", width=80)
    st.title("Navigation")
    
    menu = st.radio(
        "בחר קטגוריה / Choisir une section",
        ["📈 Tableau de bord", 
         "💰 תיק השקעות / Portefeuille", 
         "🔔 התראות מחיר / Alertes",
         "📧 התראות אימייל / Email",
         "📤 ייצוא נתונים / Export",
         "🤖 תחזיות ML / Prédictions",
         "🇮🇱 מדדי תל אביב / Indices"]
    )
    
    st.markdown("---")
    
    # Configuration commune
    st.subheader("⚙️ Configuration")
    st.caption(f"🕐 Fuseau : UTC+2 (Heure locale)")
    
    # Liste des symboles
    default_symbols = ["TEVA", "LUMI.TA", "BEZQ.TA", "NICE", "AZRG.TA"]
    
    # Sélection du symbole principal
    symbol = st.selectbox(
        "סימן / Symbole principal",
        options=st.session_state.watchlist + ["אחר / Autre..."],
        index=0
    )
    
    if symbol == "אחר / Autre...":
        symbol = st.text_input("הכנס סימן / Entrer symbole", value="TEVA").upper()
        if symbol and symbol not in st.session_state.watchlist:
            st.session_state.watchlist.append(symbol)
    
    # Note sur les suffixes
    st.caption("""
    📍 Suffixes:
    - .TA: Tel Aviv (ex: LUMI.TA)
    - Sans suffixe: US/Global (ex: TEVA)
    """)
    
    # Période et intervalle
    col1, col2 = st.columns(2)
    with col1:
        period = st.selectbox(
            "תקופה / Période",
            options=["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"],
            index=2
        )
    
    with col2:
        interval_map = {
            "1m": "1 minute", "2m": "2 minutes", "5m": "5 minutes",
            "15m": "15 minutes", "30m": "30 minutes", "1h": "1 heure",
            "1d": "1 jour", "1wk": "1 semaine", "1mo": "1 mois"
        }
        interval = st.selectbox(
            "מרווח / Intervalle",
            options=list(interval_map.keys()),
            format_func=lambda x: interval_map[x],
            index=4 if period == "1d" else 6
        )
    
    # Auto-refresh
    auto_refresh = st.checkbox("רענון אוטומטי / Auto-refresh", value=False)
    if auto_refresh:
        refresh_rate = st.slider(
            "תדירות (שניות) / Fréquence (sec)",
            min_value=5,
            max_value=60,
            value=30,
            step=5
        )

# Fonctions utilitaires
@st.cache_data(ttl=300)
def load_stock_data(symbol, period, interval):
    """Charge les données boursières"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)
        info = ticker.info
        
        # Convertir l'index en UTC+2
        if not hist.empty:
            if hist.index.tz is None:
                hist.index = hist.index.tz_localize('UTC').tz_convert(USER_TIMEZONE)
            else:
                hist.index = hist.index.tz_convert(USER_TIMEZONE)
        
        return hist, info
    except Exception as e:
        st.error(f"שגיאה / Erreur: {e}")
        return None, None

def get_exchange(symbol):
    """Détermine l'échange pour un symbole"""
    if symbol.endswith('.TA'):
        return 'Tel Aviv (TASE)'
    else:
        return 'US/Global'

def get_currency(symbol):
    """Détermine la devise pour un symbole"""
    if symbol.endswith('.TA'):
        return 'ILS'  # Shekel
    else:
        return 'USD'

def format_currency(value, symbol):
    """Formate la monnaie selon le symbole"""
    if symbol.endswith('.TA'):
        return f"₪{value:.2f}"
    else:
        return f"${value:.2f}"

def send_email_alert(subject, body, to_email):
    """Envoie une notification par email"""
    if not st.session_state.email_config['enabled']:
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = st.session_state.email_config['email']
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(
            st.session_state.email_config['smtp_server'], 
            st.session_state.email_config['smtp_port']
        )
        server.starttls()
        server.login(
            st.session_state.email_config['email'],
            st.session_state.email_config['password']
        )
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"שגיאת שליחה / Erreur d'envoi: {e}")
        return False

def check_price_alerts(current_price, symbol):
    """Vérifie les alertes de prix"""
    triggered = []
    for alert in st.session_state.price_alerts:
        if alert['symbol'] == symbol:
            if alert['condition'] == 'above' and current_price >= alert['price']:
                triggered.append(alert)
            elif alert['condition'] == 'below' and current_price <= alert['price']:
                triggered.append(alert)
    
    return triggered

def get_market_status():
    """Détermine le statut des marchés israéliens"""
    israel_now = datetime.now(ISRAEL_TIMEZONE)
    israel_hour = israel_now.hour
    israel_minute = israel_now.minute
    israel_weekday = israel_now.weekday()
    israel_date = israel_now.strftime('%Y-%m-%d')
    
    # Weekend (vendredi = 4, samedi = 5 en Python)
    if israel_weekday >= 4:
        return "סגור (סופ"ש) / Fermé (weekend)", "🔴"
    
    # Jours fériés
    if israel_date in ISRAELI_HOLIDAYS_2024:
        return "סגור (חג) / Fermé (férié)", "🔴"
    
    # Horaires TASE: Dimanche-Jeudi 09:45 - 16:25
    if (israel_hour > 9 or (israel_hour == 9 and israel_minute >= 45)) and israel_hour < 16:
        return "פתוח / Ouvert", "🟢"
    elif israel_hour == 16 and israel_minute <= 25:
        return "פתוח / Ouvert", "🟢"
    elif israel_hour == 16 and israel_minute > 25:
        return "סגור / Fermé", "🔴"
    else:
        return "סגור / Fermé", "🔴"

def safe_get_metric(hist, metric, index=-1):
    """Récupère une métrique en toute sécurité"""
    try:
        if hist is not None and not hist.empty and len(hist) > abs(index):
            return hist[metric].iloc[index]
        return 0
    except:
        return 0

# Chargement des données
hist, info = load_stock_data(symbol, period, interval)

# Vérification si les données sont disponibles
if hist is None or hist.empty:
    st.warning(f"⚠️ לא ניתן לטעון נתונים עבור {symbol} / Impossible de charger les données pour {symbol}")
    current_price = 0
else:
    current_price = safe_get_metric(hist, 'Close')
    currency_symbol = "₪" if symbol.endswith('.TA') else "$"
    
    # Vérification des alertes
    triggered_alerts = check_price_alerts(current_price, symbol)
    for alert in triggered_alerts:
        st.balloons()
        st.success(f"🎯 התראה הופעלה / Alerte déclenchée pour {symbol} à {currency_symbol}{current_price:.2f}")
        
        # Notification email
        if st.session_state.email_config['enabled']:
            subject = f"🚨 התראת מחיר / Alerte prix - {symbol}"
            body = f"""
            <h2>התראת מחיר הופעלה / Alerte de prix déclenchée</h2>
            <p><b>סימן / Symbole:</b> {symbol}</p>
            <p><b>מחיר נוכחי / Prix actuel:</b> {currency_symbol}{current_price:.2f}</p>
            <p><b>תנאי / Condition:</b> {alert['condition']} {currency_symbol}{alert['price']:.2f}</p>
            <p><b>תאריך (UTC+2) / Date:</b> {datetime.now(USER_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}</p>
            """
            send_email_alert(subject, body, st.session_state.email_config['email'])
        
        # Retirer l'alerte si elle est à usage unique
        if alert.get('one_time', False):
            st.session_state.price_alerts.remove(alert)

# ============================================================================
# SECTION 1: TABLEAU DE BORD
# ============================================================================
if menu == "📈 Tableau de bord":
    # Statut du marché
    market_status, market_icon = get_market_status()
    st.info(f"{market_icon} שוק תל אביב / Marché TASE: {market_status}")
    
    if hist is not None and not hist.empty:
        # Métriques principales
        exchange = get_exchange(symbol)
        currency = get_currency(symbol)
        st.subheader(f"📊 נתונים בזמן אמת / Aperçu temps réel - {symbol} ({exchange})")
        
        col1, col2, col3, col4 = st.columns(4)
        
        previous_close = safe_get_metric(hist, 'Close', -2) if len(hist) > 1 else current_price
        change = current_price - previous_close
        change_pct = (change / previous_close * 100) if previous_close != 0 else 0
        
        with col1:
            st.metric(
                label="מחיר נוכחי / Prix actuel",
                value=format_currency(current_price, symbol),
                delta=f"{change:.2f} ({change_pct:.2f}%)"
            )
        
        with col2:
            day_high = safe_get_metric(hist, 'High')
            st.metric("מקסימום / Plus haut", format_currency(day_high, symbol))
        
        with col3:
            day_low = safe_get_metric(hist, 'Low')
            st.metric("מינימום / Plus bas", format_currency(day_low, symbol))
        
        with col4:
            volume = safe_get_metric(hist, 'Volume')
            volume_formatted = f"{volume/1e6:.1f}M" if volume > 1e6 else f"{volume/1e3:.1f}K"
            st.metric("מחזור / Volume", volume_formatted)
        
        # Dernière mise à jour
        st.caption(f"עדכון אחרון / Dernière MAJ: {hist.index[-1].strftime('%Y-%m-%d %H:%M:%S')} UTC+2")
        
        # Graphique principal
        st.subheader("📉 התפתחות מחיר / Évolution du prix")
        
        fig = go.Figure()
        
        # Chandeliers ou ligne selon l'intervalle
        if interval in ["1m", "2m", "5m", "15m", "30m", "1h"]:
            fig.add_trace(go.Candlestick(
                x=hist.index,
                open=hist['Open'],
                high=hist['High'],
                low=hist['Low'],
                close=hist['Close'],
                name='Prix',
                increasing_line_color='#00cc96',
                decreasing_line_color='#ef553b'
            ))
        else:
            fig.add_trace(go.Scatter(
                x=hist.index,
                y=hist['Close'],
                mode='lines',
                name='Prix',
                line=dict(color='#0038b8', width=2)
            ))
        
        # Ajouter les moyennes mobiles
        if len(hist) >= 20:
            ma_20 = hist['Close'].rolling(window=20).mean()
            fig.add_trace(go.Scatter(
                x=hist.index,
                y=ma_20,
                mode='lines',
                name='MA 20',
                line=dict(color='orange', width=1, dash='dash')
            ))
        
        if len(hist) >= 50:
            ma_50 = hist['Close'].rolling(window=50).mean()
            fig.add_trace(go.Scatter(
                x=hist.index,
                y=ma_50,
                mode='lines',
                name='MA 50',
                line=dict(color='purple', width=1, dash='dash')
            ))
        
        # Volume
        fig.add_trace(go.Bar(
            x=hist.index,
            y=hist['Volume'],
            name='Volume',
            yaxis='y2',
            marker=dict(color='lightgray', opacity=0.3)
        ))
        
        # Ajouter des lignes verticales pour les heures de trading
        if interval in ["1m", "5m", "15m", "30m", "1h"] and not hist.empty:
            # Ajouter une zone pour les heures de trading TASE
            last_date = hist.index[-1].date()
            try:
                tase_open = ISRAEL_TIMEZONE.localize(datetime.combine(last_date, datetime.strptime("09:45", "%H:%M").time()))
                tase_close = ISRAEL_TIMEZONE.localize(datetime.combine(last_date, datetime.strptime("16:25", "%H:%M").time()))
                
                tase_open_utc2 = tase_open.astimezone(USER_TIMEZONE)
                tase_close_utc2 = tase_close.astimezone(USER_TIMEZONE)
                
                fig.add_vrect(
                    x0=tase_open_utc2,
                    x1=tase_close_utc2,
                    fillcolor="blue",
                    opacity=0.1,
                    layer="below",
                    line_width=0,
                    annotation_text="TASE Session"
                )
            except:
                pass
        
        fig.update_layout(
            title=f"{symbol} - {period} (שעות UTC+2 / heures UTC+2)",
            yaxis_title=f"מחיר / Prix ({'₪' if symbol.endswith('.TA') else '$'})",
            yaxis2=dict(
                title="מחזור / Volume",
                overlaying='y',
                side='right',
                showgrid=False
            ),
            xaxis_title="תאריך (UTC+2) / Date",
            height=600,
            hovermode='x unified',
            template='plotly_white'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Informations sur l'entreprise
        with st.expander("ℹ️ פרטי חברה / Informations entreprise"):
            if info:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**שם / Nom :** {info.get('longName', 'N/A')}")
                    st.write(f"**ענף / Secteur :** {info.get('sector', 'N/A')}")
                    st.write(f"**תעשייה / Industrie :** {info.get('industry', 'N/A')}")
                    st.write(f"**אתר / Site web :** {info.get('website', 'N/A')}")
                    st.write(f"**בורסה / Bourse :** {exchange}")
                    st.write(f"**מטבע / Devise :** {currency}")
                
                with col2:
                    market_cap = info.get('marketCap', 0)
                    if market_cap > 0:
                        if currency == 'ILS':
                            st.write(f"**שווי שוק / Cap :** ₪{market_cap:,.0f}")
                        else:
                            st.write(f"**שווי שוק / Cap :** ${market_cap:,.0f}")
                    else:
                        st.write("**שווי שוק / Cap :** N/A")
                    
                    st.write(f"**מכפיל רווח / P/E :** {info.get('trailingPE', 'N/A')}")
                    st.write(f"**דיבידנד / Dividende :** {info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "**דיבידנד / Dividende :** N/A")
                    st.write(f"**בטא / Beta :** {info.get('beta', 'N/A')}")
            else:
                st.write("מידע לא זמין / Informations non disponibles")
    else:
        st.warning(f"אין נתונים עבור {symbol} / Aucune donnée pour {symbol}")

# ============================================================================
# SECTION 2: PORTEFEUILLE VIRTUEL
# ============================================================================
elif menu == "💰 תיק השקעות / Portefeuille":
    st.subheader("💰 ניהול תיק השקעות וירטואלי / Gestion de portefeuille virtuel")
    
    col1, col2 = st.columns([2, 1])
    
    with col2:
        st.markdown("### ➕ הוספת פוזיציה / Ajouter position")
        with st.form("add_position"):
            symbol_pf = st.text_input("סימן / Symbole", value="TEVA").upper()
            
            # Aide sur les suffixes
            st.caption("""
            סיומות / Suffixes:
            - .TA: תל אביב / Tel Aviv
            - ללא / sans: US/Global
            """)
            
            shares = st.number_input("כמות מניות / Nombre actions", min_value=0.01, step=0.01, value=1.0)
            buy_price = st.number_input("מחיר קנייה / Prix achat", min_value=0.01, step=0.01, value=100.0)
            
            if st.form_submit_button("הוסף לתיק / Ajouter"):
                if symbol_pf and shares > 0:
                    if symbol_pf not in st.session_state.portfolio:
                        st.session_state.portfolio[symbol_pf] = []
                    
                    st.session_state.portfolio[symbol_pf].append({
                        'shares': shares,
                        'buy_price': buy_price,
                        'date': datetime.now(USER_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')
                    })
                    st.success(f"✅ {shares} מניות {symbol_pf} נוספו / actions ajoutées")
    
    with col1:
        st.markdown("### 📊 ביצועי תיק / Performance portefeuille")
        
        if st.session_state.portfolio:
            portfolio_data = []
            total_value_usd = 0
            total_cost_usd = 0
            total_value_ils = 0
            total_cost_ils = 0
            
            for symbol_pf, positions in st.session_state.portfolio.items():
                try:
                    ticker = yf.Ticker(symbol_pf)
                    hist = ticker.history(period='1d')
                    if not hist.empty:
                        current = hist['Close'].iloc[-1]
                    else:
                        current = 0
                    
                    exchange = get_exchange(symbol_pf)
                    currency = get_currency(symbol_pf)
                    
                    for pos in positions:
                        shares = pos['shares']
                        buy_price = pos['buy_price']
                        cost = shares * buy_price
                        value = shares * current
                        profit = value - cost
                        profit_pct = (profit / cost * 100) if cost > 0 else 0
                        
                        if currency == 'ILS':
                            total_cost_ils += cost
                            total_value_ils += value
                            # Conversion approximative USD/ILS pour le total (taux fixe pour l'affichage)
                            usd_rate = 3.7  # Taux approximatif
                            total_cost_usd += cost / usd_rate
                            total_value_usd += value / usd_rate
                        else:
                            total_cost_usd += cost
                            total_value_usd += value
                        
                        portfolio_data.append({
                            'סימן/Symbole': symbol_pf,
                            'בורסה/Marché': exchange,
                            'מטבע/Devise': currency,
                            'כמות/Actions': shares,
                            "מחיר קנייה/Achat": format_currency(buy_price, symbol_pf),
                            'מחיר נוכחי/Actuel': format_currency(current, symbol_pf),
                            'שווי/Valeur': format_currency(value, symbol_pf),
                            'רווח/Profit': format_currency(profit, symbol_pf),
                            'רווח %': f"{profit_pct:.1f}%"
                        })
                except Exception as e:
                    st.warning(f"לא ניתן לטעון / Impossible charger {symbol_pf}")
            
            if portfolio_data:
                # Métriques globales
                total_profit_usd = total_value_usd - total_cost_usd
                total_profit_pct_usd = (total_profit_usd / total_cost_usd * 100) if total_cost_usd > 0 else 0
                
                st.markdown("#### סה\"כ בשווי דולר / Total en USD")
                col1_1, col1_2, col1_3 = st.columns(3)
                col1_1.metric("שווי כולל/Valeur totale", f"${total_value_usd:,.2f}")
                col1_2.metric("עלות כוללת/Coût total", f"${total_cost_usd:,.2f}")
                col1_3.metric(
                    "רווח כולל/Profit total",
                    f"${total_profit_usd:,.2f}",
                    delta=f"{total_profit_pct_usd:.1f}%"
                )
                
                if total_value_ils > 0:
                    total_profit_ils = total_value_ils - total_cost_ils
                    total_profit_pct_ils = (total_profit_ils / total_cost_ils * 100) if total_cost_ils > 0 else 0
                    
                    st.markdown("#### סה\"כ בשווי שקל / Total en ILS")
                    col_ils1, col_ils2, col_ils3 = st.columns(3)
                    col_ils1.metric("שווי כולל", f"₪{total_value_ils:,.2f}")
                    col_ils2.metric("עלות כוללת", f"₪{total_cost_ils:,.2f}")
                    col_ils3.metric("רווח כולל", f"₪{total_profit_ils:,.2f}", delta=f"{total_profit_pct_ils:.1f}%")
                
                # Tableau des positions
                st.markdown("### 📋 פוזיציות מפורטות / Positions détaillées")
                df_portfolio = pd.DataFrame(portfolio_data)
                st.dataframe(df_portfolio, use_container_width=True)
                
                # Graphique de répartition
                try:
                    fig_pie = px.pie(
                        names=[p['סימן/Symbole'] for p in portfolio_data],
                        values=[float(p['שווי/Valeur'].replace('₪', '').replace('$', '').replace(',', '')) for p in portfolio_data],
                        title="התפלגות התיק / Répartition portefeuille"
                    )
                    st.plotly_chart(fig_pie)
                except:
                    st.warning("לא ניתן ליצור גרף / Impossible générer graphique")
                
                # Bouton pour vider le portefeuille
                if st.button("🗑️ רוקן תיק / Vider portefeuille"):
                    st.session_state.portfolio = {}
                    st.rerun()
            else:
                st.info("אין נתוני ביצועים / Aucune donnée performance")
        else:
            st.info("אין פוזיציות בתיק. הוסף מניות כדי להתחיל / Aucune position. Ajoutez des actions !")

# ============================================================================
# SECTION 3: ALERTES DE PRIX
# ============================================================================
elif menu == "🔔 התראות מחיר / Alertes":
    st.subheader("🔔 ניהול התראות מחיר / Gestion alertes prix")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### ➕ צור התראה חדשה / Créer alerte")
        with st.form("new_alert"):
            alert_symbol = st.text_input("סימן / Symbole", value=symbol if symbol else "TEVA").upper()
            exchange = get_exchange(alert_symbol)
            st.caption(f"בורסה/Marché: {exchange}")
            
            currency_symbol = "₪" if alert_symbol.endswith('.TA') else "$"
            default_price = float(current_price * 1.05) if current_price > 0 else 100.0
            alert_price = st.number_input(
                f"מחיר יעד / Prix cible ({currency_symbol})", 
                min_value=0.01, 
                step=0.01, 
                value=default_price
            )
            
            col_cond, col_type = st.columns(2)
            with col_cond:
                condition = st.selectbox("תנאי / Condition", ["above", "below"])
            with col_type:
                alert_type = st.selectbox("סוג / Type", ["קבוע / Permanent", "חד פעמי / Une fois"])
            
            one_time = alert_type.startswith("חד פעמי")
            
            if st.form_submit_button("צור התראה / Créer"):
                st.session_state.price_alerts.append({
                    'symbol': alert_symbol,
                    'price': alert_price,
                    'condition': condition,
                    'one_time': one_time,
                    'created': datetime.now(USER_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')
                })
                st.success(f"✅ התראה נוצרה / Alerte créée pour {alert_symbol} à {currency_symbol}{alert_price:.2f}")
    
    with col2:
        st.markdown("### 📋 התראות פעילות / Alertes actives")
        if st.session_state.price_alerts:
            for i, alert in enumerate(st.session_state.price_alerts):
                with st.container():
                    currency_symbol = "₪" if alert['symbol'].endswith('.TA') else "$"
                    st.markdown(f"""
                    <div class='alert-box alert-warning'>
                        <b>{alert['symbol']}</b> - {alert['condition']} {currency_symbol}{alert['price']:.2f}<br>
                        <small>נוצרה/Créée: {alert['created']} (UTC+2) | {('חד פעמי/Unique' if alert['one_time'] else 'קבוע/Permanent')}</small>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button(f"מחק / Supprimer", key=f"del_alert_{i}"):
                        st.session_state.price_alerts.pop(i)
                        st.rerun()
        else:
            st.info("אין התראות פעילות / Aucune alerte active")

# ============================================================================
# SECTION 4: NOTIFICATIONS EMAIL
# ============================================================================
elif menu == "📧 התראות אימייל / Email":
    st.subheader("📧 הגדרות התראות אימייל / Configuration notifications email")
    
    with st.form("email_config"):
        enabled = st.checkbox("הפעל התראות אימייל / Activer notifications", value=st.session_state.email_config['enabled'])
        
        col1, col2 = st.columns(2)
        with col1:
            smtp_server = st.text_input("שרת SMTP / Serveur SMTP", value=st.session_state.email_config['smtp_server'])
            smtp_port = st.number_input("פורט SMTP / Port SMTP", value=st.session_state.email_config['smtp_port'])
        
        with col2:
            email = st.text_input("כתובת אימייל / Adresse email", value=st.session_state.email_config['email'])
            password = st.text_input("סיסמה / Mot de passe", type="password", value=st.session_state.email_config['password'])
        
        test_email = st.text_input("אימייל לבדיקה (אופציונלי) / Email test (optionnel)")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.form_submit_button("💾 שמור הגדרות / Sauvegarder"):
                st.session_state.email_config = {
                    'enabled': enabled,
                    'smtp_server': smtp_server,
                    'smtp_port': smtp_port,
                    'email': email,
                    'password': password
                }
                st.success("ההגדרות נשמרו / Configuration sauvegardée !")
        
        with col_btn2:
            if st.form_submit_button("📨 בדיקה / Tester"):
                if test_email:
                    if send_email_alert(
                        "בדיקת התראות / Test notifications",
                        f"<h2>זוהי בדיקה</h2><p>הגדרות האימייל שלך פועלות כראוי!</p><p>שעת שליחה (UTC+2): {datetime.now(USER_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}</p>",
                        test_email
                    ):
                        st.success("אימייל בדיקה נשלח / Email test envoyé !")
                    else:
                        st.error("שליחה נכשלה / Échec envoi")
    
    # Aperçu de la configuration
    with st.expander("📋 תצוגת הגדרות / Aperçu configuration"):
        st.json(st.session_state.email_config)

# ============================================================================
# SECTION 5: EXPORT DES DONNÉES
# ============================================================================
elif menu == "📤 ייצוא נתונים / Export":
    st.subheader("📤 ייצוא נתונים / Export données")
    
    if hist is not None and not hist.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📊 נתונים היסטוריים / Données historiques")
            # Afficher avec fuseau horaire
            display_hist = hist.copy()
            display_hist.index = display_hist.index.strftime('%Y-%m-%d %H:%M:%S (UTC+2)')
            st.dataframe(display_hist.tail(20))
            
            # Export CSV
            csv = hist.to_csv()
            st.download_button(
                label="📥 הורד CSV / Télécharger CSV",
                data=csv,
                file_name=f"{symbol}_data_{datetime.now(USER_TIMEZONE).strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        
        with col2:
            st.markdown("### 📈 דוח PDF / Rapport PDF")
            st.info("יצירת דוח PDF (סימולציה) / Génération PDF (simulée)")
            
            # Statistiques
            st.markdown("**סטטיסטיקות / Statistiques:**")
            stats = {
                'ממוצע/Moyenne': hist['Close'].mean(),
                'סטיית תקן/Écart-type': hist['Close'].std(),
                'מינימום/Min': hist['Close'].min(),
                'מקסימום/Max': hist['Close'].max(),
                'שינוי כולל/Variation totale': f"{(hist['Close'].iloc[-1] / hist['Close'].iloc[0] - 1) * 100:.2f}%" if len(hist) > 1 else "N/A"
            }
            
            for key, value in stats.items():
                if isinstance(value, float):
                    st.write(f"{key}: {format_currency(value, symbol)}")
                else:
                    st.write(f"{key}: {value}")
            
            # Export JSON
            json_data = {
                'symbol': symbol,
                'exchange': get_exchange(symbol),
                'currency': get_currency(symbol),
                'last_update': datetime.now(USER_TIMEZONE).isoformat(),
                'timezone': 'UTC+2',
                'current_price': float(current_price) if current_price else 0,
                'statistics': {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in stats.items()},
                'data': hist.reset_index().to_dict(orient='records')
            }
            
            st.download_button(
                label="📥 הורד JSON / Télécharger JSON",
                data=json.dumps(json_data, indent=2, default=str),
                file_name=f"{symbol}_data_{datetime.now(USER_TIMEZONE).strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    else:
        st.warning(f"אין נתונים לייצוא עבור {symbol} / Aucune donnée à exporter pour {symbol}")

# ============================================================================
# SECTION 6: PRÉDICTIONS ML
# ============================================================================
elif menu == "🤖 תחזיות ML / Prédictions":
    st.subheader("🤖 תחזיות עם למידת מכונה / Prédictions Machine Learning")
    
    if hist is not None and not hist.empty and len(hist) > 30:
        st.markdown("### מודל חיזוי (רגרסיה פולינומית) / Modèle prédiction (Régression polynomiale)")
        
        # Note sur les spécificités israéliennes
        st.info("""
        ⚠️ יש להתחשב בגורמים מיוחדים לשוק הישראלי / Facteurs spécifiques marché israélien:
        - חגים יהודיים / Jours fériés juifs
        - מצב גאופוליטי / Situation géopolitique
        - שער החליפין שקל-דולר / Taux de change ILS/USD
        - רגולציה מקומית / Réglementation locale
        """)
        
        # Préparation des données
        df_pred = hist[['Close']].reset_index()
        df_pred['Days'] = (df_pred['Date'] - df_pred['Date'].min()).dt.days
        
        X = df_pred['Days'].values.reshape(-1, 1)
        y = df_pred['Close'].values
        
        # Configuration de la prédiction
        col1, col2 = st.columns(2)
        
        with col1:
            days_to_predict = st.slider("ימים לחיזוי / Jours à prédire", min_value=1, max_value=30, value=7)
            degree = st.slider("דרגת פולינום / Degré polynôme", min_value=1, max_value=5, value=2)
        
        with col2:
            st.markdown("### אפשרויות / Options")
            show_confidence = st.checkbox("הצג רווח בר סמך / Intervalle confiance", value=True)
        
        # Entraînement du modèle
        model = make_pipeline(
            PolynomialFeatures(degree=degree),
            LinearRegression()
        )
        model.fit(X, y)
        
        # Prédictions
        last_day = X[-1][0]
        future_days = np.arange(last_day + 1, last_day + days_to_predict + 1).reshape(-1, 1)
        predictions = model.predict(future_days)
        
        # Dates futures (en UTC+2)
        last_date = df_pred['Date'].iloc[-1]
        future_dates = [last_date + timedelta(days=i+1) for i in range(days_to_predict)]
        
        # Visualisation
        fig_pred = go.Figure()
        
        # Données historiques
        fig_pred.add_trace(go.Scatter(
            x=df_pred['Date'],
            y=y,
            mode='lines',
            name='היסטוריה/Historique',
            line=dict(color='blue')
        ))
        
        # Prédictions
        fig_pred.add_trace(go.Scatter(
            x=future_dates,
            y=predictions,
            mode='lines+markers',
            name='תחזית/Prédictions',
            line=dict(color='red', dash='dash'),
            marker=dict(size=8)
        ))
        
        # Intervalle de confiance (simulé)
        if show_confidence:
            residuals = y - model.predict(X)
            std_residuals = np.std(residuals)
            
            upper_bound = predictions + 2 * std_residuals
            lower_bound = predictions - 2 * std_residuals
            
            fig_pred.add_trace(go.Scatter(
                x=future_dates + future_dates[::-1],
                y=np.concatenate([upper_bound, lower_bound[::-1]]),
                fill='toself',
                fillcolor='rgba(255,0,0,0.2)',
                line=dict(color='rgba(255,0,0,0)'),
                name='רווח בר סמך 95% / IC 95%'
            ))
        
        fig_pred.update_layout(
            title=f"תחזיות עבור {symbol} - {days_to_predict} ימים / Prédictions {days_to_predict} jours (UTC+2)",
            xaxis_title="תאריך (UTC+2) / Date",
            yaxis_title=f"מחיר / Prix ({'₪' if symbol.endswith('.TA') else '$'})",
            hovermode='x unified',
            template='plotly_white'
        )
        
        st.plotly_chart(fig_pred, use_container_width=True)
        
        # Tableau des prédictions
        st.markdown("### 📋 תחזיות מפורטות / Prédictions détaillées")
        pred_df = pd.DataFrame({
            'תאריך (UTC+2)/Date': [d.strftime('%Y-%m-%d') for d in future_dates],
            'מחיר חזוי/Prix prédit': [format_currency(p, symbol) for p in predictions],
            'אחוז שינוי/Variation %': [f"{(p/current_price - 1)*100:.2f}%" for p in predictions]
        })
        st.dataframe(pred_df, use_container_width=True)
        
        # Métriques de performance
        st.markdown("### 📊 ביצועי מודל / Performance modèle")
        residuals = y - model.predict(X)
        mse = np.mean(residuals**2)
        rmse = np.sqrt(mse)
        mae = np.mean(np.abs(residuals))
        
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("RMSE", f"{format_currency(rmse, symbol)}")
        col_m2.metric("MAE", f"{format_currency(mae, symbol)}")
        col_m3.metric("R²", f"{model.score(X, y):.3f}")
        
        # Analyse des tendances
        st.markdown("### 📈 ניתוח מגמות / Analyse tendances")
        last_price = current_price
        last_pred = predictions[-1]
        trend = "עולה 📈 / Haussière" if last_pred > last_price else "יורדת 📉 / Baissière" if last_pred < last_price else "יציבה ➡️ / Neutre"
        
        if last_pred > last_price * 1.05:
            strength = "מגמת עלייה חזקה 🚀 / Forte haussière"
        elif last_pred > last_price:
            strength = "מגמת עלייה קלה 📈 / Légère haussière"
        elif last_pred < last_price * 0.95:
            strength = "מגמת ירידה חזקה 🔻 / Forte baissière"
        elif last_pred < last_price:
            strength = "מגמת ירידה קלה 📉 / Légère baissière"
        else:
            strength = "מגמה יציבה ⏸️ / Stable"
        
        st.info(f"**מגמה חזויה / Tendance prévue:** {trend} - {strength}")
        
        # Facteurs spécifiques Israël
        with st.expander("🇮🇱 גורמים המשפיעים על השוק הישראלי / Facteurs marché israélien"):
            st.markdown("""
            **גורמים מקרו-כלכליים / Facteurs macroéconomiques:**
            - מדיניות בנק ישראל / Politique Banque d'Israël
            - שער החליפין שקל-דולר / Taux de change ILS/USD
            - מצב גאופוליטי / Situation géopolitique
            - נתוני כלכלה (תמ\"ג, אינפלציה) / Données économiques (PIB, inflation)
            
            **חגים והשפעות / Jours fériés:**
            - חגי ישראל / Fêtes juives (Pessah, Souccot, etc.)
            - ימי שישי-שבת / Week-end (vendredi-samedi)
            - עונת הדוחות / Saison des résultats
            """)
        
    else:
        st.warning(f"אין מספיק נתונים היסטוריים עבור {symbol} (מינימום 30 נקודות) / Pas assez données pour {symbol} (min 30 points)")

# ============================================================================
# SECTION 7: INDICES TASE
# ============================================================================
elif menu == "🇮🇱 מדדי תל אביב / Indices":
    st.subheader("🇮🇱 מדדי בורסת תל אביב / Indices TASE")
    
    # Liste des indices israéliens
    israel_indices = {
        '^TA125': 'TA-125',
        '^TA35': 'TA-35',
        '^TA90': 'TA-90',
        '^TA_BANKS': 'TA-Banks',
        '^TA_OILGAS': 'TA-Oil&Gas',
        '^TA_TECH': 'TA-Technology',
        '^TA_REAL_ESTATE': 'TA-Real Estate',
        '^TA_BIO_SCIENCE': 'TA-Biomed',
        'TEVA': 'Teva (référence)',
        'LUMI.TA': 'Bank Leumi (référence)'
    }
    
    col1, col2 = st.columns([2, 1])
    
    with col2:
        st.markdown("### 🇮🇱 בחירת מדד / Sélection indice")
        selected_index = st.selectbox(
            "בחר מדד / Choisir indice",
            options=list(israel_indices.keys()),
            format_func=lambda x: f"{israel_indices[x]} ({x})",
            index=0
        )
        
        st.markdown("### 📊 ביצועי מדדים / Performance indices")
        
        # Période de comparaison
        perf_period = st.selectbox(
            "תקופת השוואה / Période comparaison",
            options=["1d", "5d", "1mo", "3mo", "6mo", "1y"],
            index=0
        )
    
    with col1:
        # Charger et afficher l'indice sélectionné
        try:
            index_ticker = yf.Ticker(selected_index)
            index_hist = index_ticker.history(period=perf_period)
            
            if not index_hist.empty:
                # Convertir en UTC+2
                if index_hist.index.tz is None:
                    index_hist.index = index_hist.index.tz_localize('UTC').tz_convert(USER_TIMEZONE)
                else:
                    index_hist.index = index_hist.index.tz_convert(USER_TIMEZONE)
                
                current_index = index_hist['Close'].iloc[-1]
                prev_index = index_hist['Close'].iloc[-2] if len(index_hist) > 1 else current_index
                index_change = current_index - prev_index
                index_change_pct = (index_change / prev_index * 100) if prev_index != 0 else 0
                
                st.markdown(f"### {israel_indices[selected_index]}")
                
                col_i1, col_i2, col_i3 = st.columns(3)
                col_i1.metric("ערך / Valeur", f"{current_index:.2f}")
                col_i2.metric("שינוי / Variation", f"{index_change:.2f}")
                col_i3.metric("אחוז שינוי / Var %", f"{index_change_pct:.2f}%", delta=f"{index_change_pct:.2f}%")
                
                st.caption(f"עדכון אחרון / Dernière MAJ: {index_hist.index[-1].strftime('%Y-%m-%d %H:%M:%S')} UTC+2")
                
                # Graphique de l'indice
                fig_index = go.Figure()
                fig_index.add_trace(go.Scatter(
                    x=index_hist.index,
                    y=index_hist['Close'],
                    mode='lines',
                    name=israel_indices[selected_index],
                    line=dict(color='#0038b8', width=2)
                ))
                
                fig_index.update_layout(
                    title=f"התפתחות / Évolution - {perf_period} (שעות UTC+2 / heures UTC+2)",
                    xaxis_title="תאריך (UTC+2) / Date",
                    yaxis_title="נקודות / Points",
                    height=400,
                    template='plotly_white'
                )
                
                st.plotly_chart(fig_index, use_container_width=True)
                
                # Statistiques de l'indice
                st.markdown("### 📈 סטטיסטיקות / Statistiques")
                col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                col_s1.metric("מקסימום / Plus haut", f"{index_hist['High'].max():.2f}")
                col_s2.metric("מינימום / Plus bas", f"{index_hist['Low'].min():.2f}")
                col_s3.metric("ממוצע / Moyenne", f"{index_hist['Close'].mean():.2f}")
                col_s4.metric("תנודתיות / Volatilité", f"{index_hist['Close'].pct_change().std()*100:.2f}%")
                
        except Exception as e:
            st.error(f"שגיאה בטעינת מדד / Erreur chargement indice: {str(e)}")
    
    # Tableau de comparaison des indices
    st.markdown("### 📊 השוואת מדדים / Comparaison indices")
    
    comparison_data = []
    for idx, name in list(israel_indices.items())[:6]:  # Limiter à 6 indices
        try:
            ticker = yf.Ticker(idx)
            hist = ticker.history(period="5d")
            if not hist.empty:
                current = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[0]
                change_pct = ((current - prev) / prev * 100) if prev != 0 else 0
                
                comparison_data.append({
                    'מדד/Indice': name,
                    'סימן/Symbole': idx,
                    'ערך/Valeur': f"{current:.2f}",
                    'שינוי 5 ימים/Var 5j': f"{change_pct:.2f}%",
                    'כיוון/Direction': '📈' if change_pct > 0 else '📉' if change_pct < 0 else '➡️'
                })
        except:
            pass
    
    if comparison_data:
        df_comparison = pd.DataFrame(comparison_data)
        st.dataframe(df_comparison, use_container_width=True)
    
    # Notes sur les indices israéliens
    with st.expander("ℹ️ אודות מדדי תל אביב / À propos indices TASE"):
        st.markdown("""
        **מדדי בורסת תל אביב / Principaux indices TASE:**
        
        - **TA-35** : 35 החברות הגדולות / 35 plus grandes capitalisations
        - **TA-125** : 125 החברות הגדולות / 125 plus grandes capitalisations
        - **TA-90** : 90 החברות הבאות après TA-35
        - **TA-Banks** : מניות הבנקים / Banques
        - **TA-Technology** : מניות טכנולוגיה / Technologie
        - **TA-Real Estate** : מניות נדל"ן / Immobilier
        - **TA-Biomed** : מניות ביומד / Biomédical
        
        **שעות מסחר (שעון ישראל) / Horaires trading (heure Israël):**
        - ראשון-חמישי / Dimanche-Jeudi: 09:45 - 16:25
        - שישי-שבת / Vendredi-Samedi: סגור / Fermé
        - חגים / Jours fériés: סגור / Fermé
        
        **המרה ל-UTC+2 / Correspondance UTC+2:**
        - פתיחה / Ouverture: 08:45 (חורף/hiver) / 07:45 (קיץ/été)
        - נעילה / Fermeture: 15:25 (חורף/hiver) / 14:25 (קיץ/été)
        """)

# ============================================================================
# WATCHLIST ET DERNIÈRE MISE À JOUR
# ============================================================================
st.markdown("---")
col_w1, col_w2 = st.columns([3, 1])

with col_w1:
    st.subheader("📋 רשימת מעקב / Watchlist")
    
    # Organiser la watchlist par marché
    tase_stocks = [s for s in st.session_state.watchlist if s.endswith('.TA')]
    us_stocks = [s for s in st.session_state.watchlist if not s.endswith('.TA')]
    
    tabs = st.tabs(["תל אביב / TASE", "ארה\"ב / US"])
    
    with tabs[0]:
        if tase_stocks:
            cols_per_row = 4
            for i in range(0, len(tase_stocks), cols_per_row):
                cols = st.columns(min(cols_per_row, len(tase_stocks) - i))
                for j, sym in enumerate(tase_stocks[i:i+cols_per_row]):
                    with cols[j]:
                        try:
                            ticker = yf.Ticker(sym)
                            hist = ticker.history(period='1d')
                            if not hist.empty:
                                price = hist['Close'].iloc[-1]
                                st.metric(sym, f"₪{price:.2f}")
                            else:
                                st.metric(sym, "N/A")
                        except:
                            st.metric(sym, "N/A")
        else:
            st.info("אין מניות תל אביב / Aucune action TASE")
    
    with tabs[1]:
        if us_stocks:
            cols_per_row = 4
            for i in range(0, len(us_stocks), cols_per_row):
                cols = st.columns(min(cols_per_row, len(us_stocks) - i))
                for j, sym in enumerate(us_stocks[i:i+cols_per_row]):
                    with cols[j]:
                        try:
                            ticker = yf.Ticker(sym)
                            hist = ticker.history(period='1d')
                            if not hist.empty:
                                price = hist['Close'].iloc[-1]
                                st.metric(sym, f"${price:.2f}")
                            else:
                                st.metric(sym, "N/A")
                        except:
                            st.metric(sym, "N/A")
        else:
            st.info("אין מניות ארה\"ב / Aucune action US")

with col_w2:
    # Heures actuelles
    utc2_time = datetime.now(USER_TIMEZONE)
    israel_time = datetime.now(ISRAEL_TIMEZONE)
    us_time = datetime.now(US_TIMEZONE)
    
    st.caption(f"🕐 UTC+2: {utc2_time.strftime('%H:%M:%S')}")
    st.caption(f"🇮🇱 ישראל: {israel_time.strftime('%H:%M:%S')}")
    st.caption(f"🇺🇸 NY: {us_time.strftime('%H:%M:%S')}")
    
    # Statut des marchés
    market_status, market_icon = get_market_status()
    st.caption(f"{market_icon} תל אביב / TASE: {market_status}")
    
    st.caption(f"עדכון אחרון / Dernière MAJ: {datetime.now(USER_TIMEZONE).strftime('%H:%M:%S')} UTC+2")
    
    if auto_refresh and hist is not None and not hist.empty:
        time.sleep(refresh_rate)
        st.rerun()

# Footer
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: gray; font-size: 0.8rem;'>"
    "🇮🇱 Tracker Bourse Israël - TASE | נתונים מ-yfinance / Données yfinance | "
    "⚠️ ייתכן עיכוב בנתונים / Données avec délai possible | "
    "🕐 כל השעות ב-UTC+2 / Tous les horaires en UTC+2"
    "</p>",
    unsafe_allow_html=True
)
