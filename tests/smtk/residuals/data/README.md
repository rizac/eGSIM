residuals_test_esm_data.csv was created as flatfile from a test example of smtk
To build it we performed the following steps:

Go to rizac smtk, tests/residuals/residuals_test.py test_residuals_execution
Put a Breakpoint in residuals/gmpe_residuals.py on line 358 in get_residuals.
after contexts are created, open PyCharm debugger console 
and write:
d= pd.concat([pd.DataFrame({'event_id' : c['EventID']} | {a: getattr(c['Ctx'], a) for a in dir(c['Ctx']) if isinstance(getattr(c['Ctx'],a), (np.generic, np.ndarray, float, int))} | {'PGA': c['Observations']['PGA'], 'SA(1.0)': c['Observations']['SA(1.0)'] }) for c in contexts])
d.to_csv('...egsim/tests/smtk/residuals/data/residual_tests_esm_data.csv', sep=';')

After that, rename ztor as depth_top_of_rupture and mag as magnitude