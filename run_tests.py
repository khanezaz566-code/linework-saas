import sys, pathlib, unittest
# Add project root to sys.path
project_root = pathlib.Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
# Discover and run tests
loader = unittest.TestLoader()
stream = open('test_output.txt', 'w')
result = unittest.TextTestRunner(stream=stream, verbosity=2).run(loader.discover('tests'))
stream.close()
print('Tests run, result:', result)
