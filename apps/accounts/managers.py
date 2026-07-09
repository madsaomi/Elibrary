from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    def create_user(self, login=None, password=None, **extra_fields):
        extra_fields.pop('is_superuser', None)
        extra_fields.pop('is_staff', None)
        user = self.model(login=login, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, login, password=None, **extra_fields):
        extra_fields.pop('is_superuser', None)
        extra_fields.pop('is_staff', None)
        user = self.model(
            login=login,
            is_staff=True,
            is_superuser=True,
            role='superadmin',
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user
