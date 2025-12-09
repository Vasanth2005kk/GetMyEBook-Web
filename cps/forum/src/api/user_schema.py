from cps.forum import ma
from cps.ub import User


class UserSchema(ma.SQLAlchemySchema):
    class Meta:
        model = User
        fields = ("profile_picture", "name", "email")
        load_instance = False  # Don't try to load instance since it's a different DB session

    id = ma.auto_field()
    name = ma.auto_field()
    email = ma.auto_field()

