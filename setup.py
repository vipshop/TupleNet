import sys, os
import setuptools
import shutil

TP_PKT_CONTROLLER_PATH = "src/tuplenet/pkt_controller/pkt_controller"
TP_CNM_PATH = "src/control/bin/tpcnm"
TP_CTL_PATH = "src/control/bin/tpctl"
TP_CNI_PATH = "src/control/bin/tpcni"

with open("README.md", "r") as readme:
    long_description = readme.read()

current_dir = os.path.dirname(os.path.abspath(__file__))
version_dir = os.path.join(current_dir, "src/tuplenet")
sys.path.append(version_dir)
import version
print("tuplenet current version:%s" % version.__version__)
egg_path = os.path.join(current_dir, 'src/tuplenet.egg-info/')
build_path = os.path.join(current_dir, 'build')
def remove_tmpfiles():
    if os.path.exists(egg_path):
        print("remove egg path:%s" % egg_path)
        shutil.rmtree(egg_path)

    if os.path.exists(build_path):
        print("remove build path:%s" % build_path)
        shutil.rmtree(build_path)

def check_essential_ext_files():
    if not os.path.exists(TP_PKT_CONTROLLER_PATH):
        print("cannot found pkt_controller, please build it first")
        sys.exit(-1)

    if not os.path.exists(TP_CNM_PATH) or \
       not os.path.exists(TP_CNI_PATH) or \
       not os.path.exists(TP_CTL_PATH):
        print("cannot found tpctl or tpcnm,tpcni , please build it first")
        sys.exit(-1)

remove_tmpfiles()
check_essential_ext_files()

setuptools.setup(
    name = "tuplenet",
    keywords = "tuplenet ovs networking",
    version = version.__version__,
    author = "zhenyu gao",
    author_email = "sysugaozhenyu@gmail.com",
    description = "A system to support virtual networking base on ovs",
    license="Apache-2.0",
    long_description = long_description,
    long_description_content_type = "text/markdown",
    url = "https://github.com/vipshop/TupleNet",
    packages = setuptools.find_packages('src'),
    package_dir = {'':'src'},
    classifiers = [
        'Development Status :: 4 - beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache License 2.0',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        ],
    install_requires = ['pyDatalog', 'etcd3'],
    package_data = {'tuplenet':['pkt_controller/pkt_controller'],},
    entry_points = {'console_scripts':['tuplenet = tuplenet.lcp:run_tuplenet']},
    scripts = [TP_CNM_PATH, TP_CNI_PATH, TP_CTL_PATH],
    )


