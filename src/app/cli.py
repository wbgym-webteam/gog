import click
from flask.cli import with_appcontext
from .models import User, Admin, db
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#defines and creates function for creating admin account
@click.command('create-admin')
@with_appcontext
def create_admin_command():
    """Create a new admin user"""
    click.echo('Create admin account')
    username = click.prompt('Username')

    # Check if username already taken in admins table
    if Admin.query.filter_by(username=username).first():
        click.echo('Error: An admin with this username already exists')
        return

    # Also prevent collision with regular user usernames
    if User.query.filter_by(username=username).first():
        click.echo('Error: A regular user with this username already exists')
        return

    first_name = click.prompt('First name')
    last_name = click.prompt('Last name')

    password = click.prompt('Password', hide_input=True)
    password2 = click.prompt('Password (again)', hide_input=True)
    if password != password2:
        click.echo("Error: Passwords don't match")
        return
    if len(password) < 8:
        click.echo("Error: Password must be at least 8 characters long")
        return

    try:
        admin = Admin(username=username, first_name=first_name, last_name=last_name)
        admin.set_password(password)
        logger.info(f"Password for admin '{username}' hashed successfully")
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Admin user '{username}' created successfully!")
    except Exception as e:
        db.session.rollback()
        click.echo(f"Error creating admin user: {str(e)}")

#defines command for listing all admin accounts
@click.command('list-admins')
@with_appcontext
def list_admins_command():
    """List all admin accounts in the system"""
    admins = Admin.query.all()
    if not admins:
        click.echo('No admin accounts found.')
        return

    click.echo('Admin accounts:')
    for admin in admins:
        click.echo(f'Username: {admin.username} | Name: {admin.first_name} {admin.last_name}')

#defines command and function for deleting admin account
@click.command('delete-admin')
@with_appcontext
def delete_admin_command():
    """Delete an admin account by username"""
    username = click.prompt('Enter username of admin to delete')

    admin = Admin.query.filter_by(username=username).first()
    if not admin:
        click.echo('Error: No admin account found with that username')
        return

    if not click.confirm(f'Are you sure you want to delete admin user "{username}"?'):
        click.echo('Deletion cancelled')
        return

    try:
        db.session.delete(admin)
        db.session.commit()
        click.echo(f'Admin user "{username}" has been deleted successfully')
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error deleting admin user: {str(e)}')

@click.command('reset-all')
@with_appcontext
def reset_all_command():
    """Reset all data except admin accounts"""
    if not click.confirm('WARNING: This will delete all regular users, games, logs, teams, and reset rankings.\nAre you sure?'):
        click.echo('Operation cancelled')
        return

    try:
        from .models import Log
        Log.query.delete()
        click.echo('Deleted all logs')

        from .models import GamePoints
        GamePoints.query.delete()
        click.echo('Deleted all game points')

        from .models import Game
        Game.query.delete()
        click.echo('Deleted all games')

        from .models import Teams
        Teams.query.delete()
        click.echo('Deleted all teams')

        # Delete all regular users (admins are in a separate table and are preserved)
        User.query.delete()
        click.echo('Deleted all regular users')

        db.session.commit()
        click.echo('All data has been reset successfully!')
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error resetting data: {str(e)}')


@click.command('help')
@with_appcontext
def help_command():
    """Show available Flask commands"""
    click.echo('Available Flask commands:')
    click.echo('  flask create-admin    Create a new admin user')
    click.echo('  flask list-admins     List all admin accounts')
    click.echo('  flask delete-admin    Delete an admin account')
    click.echo('  flask reset-all       Reset all data except admin accounts')
    click.echo('  flask help            Show this help message')

def init_app(app):
    """Register CLI commands"""
    app.cli.add_command(create_admin_command)
    app.cli.add_command(list_admins_command)
    app.cli.add_command(delete_admin_command)
    app.cli.add_command(reset_all_command)
    app.cli.add_command(help_command)
