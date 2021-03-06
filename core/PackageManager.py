#!/usr/bin/env python
# Author P G Jones - 12/05/2012 <p.g.jones@qmul.ac.uk> : First revision
# Author P G Jones - 25/07/2012 <p.g.jones@qmul.ac.uk> : Refactor for multiple dependency versions
# Base class package manager
import SystemPackage
import LocalPackage
import os
import inspect
import Log
import Exceptions
import PackageUtil
import types

class PackageManager( object ):
    """ Manages a dictionary of packages that the software can install."""
    def __init__( self ):
        """ Initialise with an empty dict."""
        self._Packages = {}
        return
    def RegisterPackage( self, package ):
        """ Register the package."""
        Log.Info( "Registering package %s" % package.GetName() )
        package.CheckState()
        self._Packages[package.GetName()] = package
        return
    def RegisterPackagesInDirectory( self, folderPath ):
        """ Register all the packages in the folderPath. """
        for module in os.listdir( folderPath ):
            if module[-3:] != '.py':
                continue
            packageSet = __import__( module[:-3], locals(), globals() )
            for name, obj in inspect.getmembers( packageSet ):
                if inspect.isclass( obj ):
                    self.RegisterPackage( obj() )
        return
    def CheckPackage( self, packageName ):
        """ Check if a package is installed, minimal logging. Returns True or False."""
        if not packageName in self._Packages.keys():
            Log.Error( "Package %s not found" % packageName )
            raise Exceptions.InstallException( "Package not found", packageName )
        return self._Packages[packageName].IsInstalled()
    # Helpful ALL functions
    def CheckAll( self ):
        """ Check all packages for install state."""
        for packageName, package in self._Packages.iteritems():
            Log.Info( "Checking package %s install status" % packageName )
            if self.CheckPackage( packageName ):
                Log.Result( "Installed" )
            else:
                Log.Warn( "Not Installed" )
        return
    def InstallAll( self ):
        """ Install all the packages."""
        for packageName, package in self._Packages.iteritems():
            if not isinstance( package, SystemPackage.SystemPackage ):
                self.InstallPackage( packageName )
        return
    def UpdateAll( self ):
        """ Update all the installed packages."""
        for packageName, package in self._Packages.iteritems():
            if package.IsInstalled() and not isinstance( package,SystemPackage.SystemPackage ):
                self.UpdatePackage( packageName )
        return
    # Now the package installers
    def InstallPackage( self, packageName ):
        """ Install the package named packageName. Must raise if package is not installed!"""
        # First check if installed
        if self.CheckPackage( packageName ):
            package = self._Packages[packageName]
            return package.GetInstallPath()
        package = self._Packages[packageName]
        # Now check if it can be installed
        if isinstance( package, LocalPackage.LocalPackage ):
            # First install the dependencies
            dependencies = self._InstallDependencies( package )
            # Now install the package
            package.SetDependencyPaths( dependencies )
            Log.Info( "Installing %s" % package.GetName() )
            try:
                package.Install()
            except Exceptions.PackageException, e:
                Log.Warn( e.Pipe )
            package.CheckState()
            if not package.IsInstalled():
                Log.Error( "Package: %s, errored during install." % package.GetName() )
                raise Exceptions.InstallException( "Failed to install", package.GetName() )
            Log.kLogFile.Write( "Package: %s installed.\n" % package.GetName() )
            Log.Result( "Package: %s installed." % package.GetName() )
            return package.GetInstallPath()            
        else: # Cannot be installed, raise error
            Log.Error( "Package %s cannot be installed by snoing, please install manually." % packageName )
            Log.Detail( package.GetHelpText() )
            raise Exceptions.InstallException( "Cannot install", packageName )

    def InstallDependencies( self, packageName ):
        """ Install the dependencies for named package."""
        if not packageName in self._Packages.keys():
            Log.Error( "Package %s not found" % packageName )
            raise Exceptions.InstallException( "Package not found", packageName )
        self._InstallDependencies( self._Packages[packageName] )
        return

    def _InstallDependencies( self, package ):
        """ Install the dependencies (if required)."""
        dependencyDict = {} # Return dictionary of dependencies
        for dependency in package.GetDependencies():
            if isinstance( dependency, types.ListType ): # Multiple optional dependencies
                for optionalDependency in dependency:
                    if self.CheckPackage( optionalDependency ): # Great found one!
                        dependencyDict[optionalDependency] = self._Packages[optionalDependency].GetInstallPath()
                        break
                else: # No optional dependency is installed, thus install the first
                    dependencyDict[dependency[0]] = self.InstallPackage( dependency[0] )
            else: # Just a single dependency
                if self.CheckPackage( dependency ):
                    dependencyDict[dependency] = self._Packages[dependency].GetInstallPath()
                else: # Must install it
                    dependencyDict[dependency] = self.InstallPackage( dependency )
        # Massive success, return dict of install paths
        return dependencyDict

    # Now the package uninstaller
    def RemovePackage( self, packageName, force = False ):
        """ Remove a package, force remove if necessary."""
        if not self.CheckPackage( packageName ):
            Log.Error( "Package %s is not installed." % packageName )
            raise Exceptions.InstallException( "Package not installed", packageName )
        package = self._Packages[packageName]
        if not force: # Check nothing depends on it, loop over packages
            for testName, testPackage in self._Packages.iteritems():
                if testPackage.IsInstalled() and not isinstance( testPackage, SystemPackage.SystemPackage ): # Check if package to be deleted is a dependecy of testPackage
                    for dependency in testPackage.GetDependencies():
                        if isinstance( dependency, types.ListType ):
                            if packageName in dependency:
                                Log.Error( "Cannot remove %s as %s depends on it." % ( packageName, testPackage.GetName() ) )
                                raise Exceptions.InstallException( "Cannot remove", packageName )
                        elif dependency == packageName:
                            Log.Error( "Cannot remove %s as %s depends on it." % ( packageName, testPackage.GetName() ) )
                            raise Exceptions.InstallException( "Cannot remove", packageName )
        # If get here then package can be deleted
        package.Remove()
        Log.Result( "Deleted %s" % packageName )
        return

    # Now the package updater
    def UpdatePackage( self, packageName ):
        """ Update a package and all packages that depend on it."""
        if not packageName in self._Packages.keys():
            Log.Error( "Package %s not found" % packageName )
            raise Exceptions.InstallException( "Package not found", packageName )
        package = self._Packages[packageName]
        if isinstance( package, SystemPackage.SystemPackage ):
            Log.Error( "Snoing cannot update %s, please update manually." % packageName )
            raise Exceptions.InstallException( "Cannot update", packageName )
        if package.IsUpdated(): # Nothing todo if already updated
            return
        Log.Info( "Updating %s" % packageName )
        dependencies = self._InstallDependencies( package )
        package.SetDependencyPaths( dependencies )
        package.Update()
        Log.Result( "Updated %s" % packageName )
        # Now update the packages that depend on this
        for testName, testPackage in self._Packages.iteritems():
             if testPackage.IsInstalled() and not isinstance( testPackage, SystemPackage.SystemPackage ): # Check if package to be deleted is a dependecy of testPackage
                 for dependency in testPackage.GetDependencies():
                     if isinstance( dependency, types.ListType ):
                         if packageName in dependency: # Update this package
                             self.UpdatePackage( testName )
                     elif dependency == packageName:
                         self.UpdatePackage( testName )
        return
