from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter()


@router.get("/family/tree", response_class=HTMLResponse)
def family_tree(db: Session = Depends(get_db)):

    result = db.execute(text("""
    SELECT 
        p1_i.first_name || ' ' || COALESCE(p1_i.last_name, ''),
        p2_i.first_name || ' ' || COALESCE(p2_i.last_name, ''),
        c_i.first_name || ' ' || COALESCE(c_i.last_name, '')
    FROM "Unions" u
    LEFT JOIN "People" p1 ON u.partner1_id = p1.person_id
    LEFT JOIN "People" p2 ON u.partner2_id = p2.person_id
    LEFT JOIN "People_I18n" p1_i ON p1.person_id = p1_i.person_id AND p1_i.lang_code='ru'
    LEFT JOIN "People_I18n" p2_i ON p2.person_id = p2_i.person_id AND p2_i.lang_code='ru'
    LEFT JOIN "UnionChildren" uc ON uc.union_id = u.id
    LEFT JOIN "People" c ON uc.child_id = c.person_id
    LEFT JOIN "People_I18n" c_i ON c.person_id = c_i.person_id AND c_i.lang_code='ru'
    ORDER BY u.id
    """))

    rows = result.fetchall()

    html = """
    <html>
    <head>
        <title>Family Tree</title>
        <style>
            body { font-family: Arial; padding: 30px; }
            h1 { margin-bottom: 30px; }
            h2 { margin-top: 25px; }
            ul { margin-top: 10px; padding-left: 20px; }
            li { margin-bottom: 5px; }
        </style>
    </head>
    <body>
    <h1>Family Tree</h1>
    """

    current = None

    for p1, p2, child in rows:
        key = f"{p1} + {p2}"
        if key != current:
            if current is not None:
                html += "</ul>"
            html += f"<h2>{key}</h2><ul>"
            current = key
        if child:
            html += f">{child}</li>"

    if current is not None:
        html += "</ul>"

    html += "</body></html>"

    return html
