from datetime import datetime, timedelta

def analyze_trend(stock):
    """Calculates stock price trend over 1 day, 1 week, and 1 month."""
    now = datetime.now()
    history = stock.historical_prices
    timestamps = sorted(history.keys(), reverse=True)

    def get_price_ago(days):
        """Finds the closest recorded price from X days ago."""
        target_time = now - timedelta(days=days)
        for timestamp in timestamps:
            time_obj = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            if time_obj <= target_time:
                return history[timestamp]
        return None

    price_1d_ago = get_price_ago(1)
    price_1w_ago = get_price_ago(7)
    price_1m_ago = get_price_ago(30)

    return {
        "1_day_change": round((stock.price - price_1d_ago) / price_1d_ago * 100, 2) if price_1d_ago else None,
        "1_week_change": round((stock.price - price_1w_ago) / price_1w_ago * 100, 2) if price_1w_ago else None,
        "1_month_change": round((stock.price - price_1m_ago) / price_1m_ago * 100, 2) if price_1m_ago else None
    }
