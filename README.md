# URBANopt DES

Text TK

## Release Instructions

1. Create a branch named `Release 0.x.`
1. Update version in pyproject.toml
1. Update CHANGELOG using GitHub's "Autogenerate Change Log" feature, using `develop` as the target
1. After tests pass, merge branch into develop
1. From local command line, merge develop into main with: `git checkout main; git pull; git merge --ff-only origin develop; git push`
1. In GitHub, tag the release against main. Copy and paste the changelog entry into the notes. Verify the release is posted to PyPI.
