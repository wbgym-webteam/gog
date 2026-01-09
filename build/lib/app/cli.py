import click
from flask.cli import with_appcontext
from .models import User, Admin, db  # Import Admin model
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#defines and creates function for creating admin accound
@click.command('create-admin')
@with_appcontext
def create_admin_command():
    """Create a new admin user"""
    click.echo('Create admin account')
    username = click.prompt('Username')
    
    # Check if user exists
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        if existing_user.is_admin:
            click.echo('Error: An admin with this username already exists')
        else:
            click.echo('Error: Username exists but is not an admin')
        return
    
    password = click.prompt('Password', hide_input=True)
    password2 = click.prompt('Password (again)', hide_input=True)
    if password != password2:
        click.echo("Error: Passwords don't match")
        return
    if len(password) < 8:
        click.echo("Error: Password must be at least 8 characters long")
        return

    try:
        user = Admin(username=username)
        user.set_password(password)
        logger.info(f"Password for user '{username}' hashed successfully")
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin user '{username}' created successfully!")
    except Exception as e:
        db.session.rollback()
        click.echo(f"Error creating admin user: {str(e)}")

#defines command for listing all admin accound
@click.command('list-admins')
@with_appcontext
def list_admins_command():
    """List all admin accounts in the system"""
    admins = User.query.filter_by(is_admin=True).all()
    if not admins:
        click.echo('No admin accounts found.')
        return
    
    click.echo('Admin accounts:')
    for admin in admins:
        click.echo(f'Username: {admin.username}')

#defines command and function for deleting admin accound
@click.command('delete-admin')
@with_appcontext
def delete_admin_command():
    """Delete an admin account by username"""
    username = click.prompt('Enter username of admin to delete')
    
    # Find the admin user
    user = User.query.filter_by(username=username, is_admin=True).first()
    if not user:
        click.echo('Error: No admin account found with that username')
        return
    
    # Confirm deletion
    if not click.confirm(f'Are you sure you want to delete admin user "{username}"?'):
        click.echo('Deletion cancelled')
        return
    
    try:
        db.session.delete(user)
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
        # Delete all logs first due to foreign key constraints
        from .models import Log
        Log.query.delete()
        click.echo('Deleted all logs')

        # Delete all game points
        from .models import GamePoints
        GamePoints.query.delete()
        click.echo('Deleted all game points')

        # Delete all games
        from .models import Game
        Game.query.delete()
        click.echo('Deleted all games')

        # Delete all teams
        from .models import Teams
        Teams.query.delete()
        click.echo('Deleted all teams')

        # Delete all regular users (non-admin)
        User.query.filter_by(is_admin=False).delete()
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
