from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length
from cps.forum.database.models import Category
from cps.forum.src.utilities.helpers import cached_categories

class ThreadCreationForm(FlaskForm):
    title = StringField("Question Title", validators=[DataRequired(), Length(max=100)])
    content = TextAreaField("Content", validators=[DataRequired(), Length(min=10)])
    category_id = SelectField("Category", validators=[DataRequired()], coerce=int)
    submit = SubmitField("Create")

    def __init__(self, *args, **kwargs):
        super(ThreadCreationForm, self).__init__(*args, **kwargs)
        try:
            self.category_id.choices = [(category.get("id"), category.get("name")) for category in cached_categories()]
        except Exception:
            self.category_id.choices = []


