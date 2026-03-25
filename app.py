import logging
import os

from flask import Flask, render_template, request, send_file

from config import Config
from models.database import (
    CraftingStation,
    Event,
    GunCode,
    ScrapeLog,
    Weapon,
    WeaponCategory,
    get_session,
    init_db,
)
from scraper.scheduler import init_scheduler, run_full_scrape
from services.export import export_all_to_excel, export_weapon_to_excel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

app = Flask(__name__)
app.config.from_object(Config)


@app.context_processor
def inject_globals():
    session = get_session()
    try:
        last_log = (
            session.query(ScrapeLog)
            .filter_by(status="success")
            .order_by(ScrapeLog.finished_at.desc())
            .first()
        )
        return {"last_scrape": last_log.finished_at if last_log else None}
    finally:
        session.close()


@app.route("/")
def home():
    session = get_session()
    try:
        categories = session.query(WeaponCategory).order_by(WeaponCategory.sort_order).all()
        weapons = session.query(Weapon).order_by(Weapon.name).all()
        stations = session.query(CraftingStation).order_by(CraftingStation.id).all()
        event = session.query(Event).order_by(Event.scraped_at.desc()).first()
        return render_template(
            "home.html",
            categories=categories,
            weapons=weapons,
            stations=stations,
            event=event,
        )
    finally:
        session.close()


@app.route("/weapons/<slug>")
def weapon_detail(slug):
    session = get_session()
    try:
        weapon = session.query(Weapon).filter_by(slug=slug).first()
        if not weapon:
            return "\u6b66\u5668\u672a\u627e\u5230", 404
        codes = (
            session.query(GunCode)
            .filter_by(weapon_id=weapon.id)
            .order_by(GunCode.copy_count.desc())
            .all()
        )
        return render_template("weapon_detail.html", weapon=weapon, codes=codes)
    finally:
        session.close()


@app.route("/api/partials/weapons")
def partial_weapons():
    session = get_session()
    try:
        query = session.query(Weapon)
        category = request.args.get("category")
        search = request.args.get("search", "").strip()

        if category:
            cat = session.query(WeaponCategory).filter_by(slug=category).first()
            if cat:
                query = query.filter_by(category_id=cat.id)

        if search:
            query = query.filter(Weapon.name.like(f"%{search}%"))

        weapons = query.order_by(Weapon.name).all()
        return render_template("partials/weapon_grid.html", weapons=weapons)
    finally:
        session.close()


@app.route("/api/partials/codes/<slug>")
def partial_codes(slug):
    session = get_session()
    try:
        weapon = session.query(Weapon).filter_by(slug=slug).first()
        if not weapon:
            return "\u6b66\u5668\u672a\u627e\u5230", 404

        sort = request.args.get("sort", "copy_count")
        query = session.query(GunCode).filter_by(weapon_id=weapon.id)

        if sort == "likes":
            query = query.order_by(GunCode.likes.desc())
        elif sort == "value":
            query = query.order_by(GunCode.value.desc())
        else:
            query = query.order_by(GunCode.copy_count.desc())

        codes = query.all()
        return render_template("partials/code_table.html", codes=codes)
    finally:
        session.close()


@app.route("/export/excel")
def export_excel():
    filepath = export_all_to_excel()
    return send_file(filepath, as_attachment=True, download_name="\u4e09\u89d2\u6d32\u6539\u67aa\u7801\u5168\u90e8\u6570\u636e.xlsx")


@app.route("/export/excel/<slug>")
def export_weapon_excel(slug):
    filepath = export_weapon_to_excel(slug)
    if not filepath:
        return "\u6b66\u5668\u672a\u627e\u5230", 404
    return send_file(filepath, as_attachment=True, download_name=f"{slug}_\u6539\u67aa\u7801.xlsx")


@app.route("/admin/scrape", methods=["POST"])
def trigger_scrape():
    import threading
    t = threading.Thread(target=run_full_scrape, daemon=True)
    t.start()
    return "\u722c\u53d6\u4efb\u52a1\u5df2\u542f\u52a8", 202


def create_app():
    os.makedirs(Config.EXPORT_DIR, exist_ok=True)
    init_db(Config.SQLALCHEMY_DATABASE_URI)
    init_scheduler()
    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=5000, debug=Config.DEBUG)
