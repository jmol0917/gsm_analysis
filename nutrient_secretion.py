"""
Created by Juan M.
on 26/03/2021
"""

"""
This script assesses nutrient production from microbial GSMs in SBML format. Microbes in the set are 'forced' (nutrient 
secretion is set as a constraint) to secrete a given nutrient (not present in the medium) 
from a specified set of nutrients and clusters are divided into sub-clusters based on individual nutrient secretion 
profile.
"""

import cobra
from cobra.exceptions import OptimizationError
import pandas as pd
import seaborn as sns
import os
import warnings
from os import listdir
from os.path import isfile, join

warnings.filterwarnings("error")

path_in = ''
path_out = ''

output_folder = ''

if not os.path.exists(path_out + output_folder):
    os.makedirs(path_out + output_folder)
    os.makedirs(path_out + output_folder + 'graphs/')
    os.makedirs(path_out + output_folder + 'compilation/')
    os.makedirs(path_out + output_folder + 'cluster/')

# Dictionary with experimental energy sources
simple_sugars = {
    # Example
    'D-glucose': "EX_glc_D(e)"
                 }

amino_acids = {
               }

cations = {
}

anions = {
}

metals = {
}

main_cofactors = {
}

secondary_cofactors = {
}

dipeptide = {
}

fatty_acids = {
}

bile_acids = {
}

other = {
}

# nutrients from every group are added to the media. Nutrients inspected for production are removed from the media
# below
rich_media_no_explored_n = {}
rich_media_no_explored_n.update(simple_sugars)
rich_media_no_explored_n.update(amino_acids)
rich_media_no_explored_n.update(main_cofactors)
rich_media_no_explored_n.update(other)
rich_media_no_explored_n.update(bile_acids)
rich_media_no_explored_n.update(fatty_acids)
rich_media_no_explored_n.update(dipeptide)
rich_media_no_explored_n.update(secondary_cofactors)
rich_media_no_explored_n.update(metals)
rich_media_no_explored_n.update(anions)
rich_media_no_explored_n.update(cations)

explored_groups = {
    # Example
    'B1': {'thiamine': "EX_thm(e)", 'thiamine monophosphate': "EX_thmmp(e)"},
}

# Creates a list of bacteria names (models) located in the path_in directory when running several microbes at once
models_in = [f for f in listdir(path_in) if isfile(join(path_in, f))]
models_in = [os.path.splitext(f)[0] for f in models_in]

rich_media_df = pd.DataFrame()

for ingredient in rich_media_no_explored_n:
    code = rich_media_no_explored_n[ingredient]
    new_ingredient = pd.DataFrame([100], index=[code])
    rich_media_df = pd.concat([rich_media_df, new_ingredient])

production_boolean_table = pd.DataFrame()

for name in models_in:
    microbe_boolean_table = pd.DataFrame()
    print(name)

    for explored_group in explored_groups:
        model = cobra.io.read_sbml_model(path_in + name + '.xml')
        media_dict = rich_media_df.to_dict()
        uptakes = media_dict[0]

        group_of_reactions = explored_groups[explored_group]

        # clear reactions that belong to the same group from the media above
        for metabolite in group_of_reactions:
            reaction = group_of_reactions[metabolite]
            if reaction in uptakes:
                del uptakes[reaction]

        # value is out of the lower loop, so if value changes for one of the reactions in the current group it
        # conserves a value of 1 even if the later reactions in the group don't return a positive outcome.
        value = 0

        for metabolite in group_of_reactions:
            reaction = group_of_reactions[metabolite]
            with model:
                medium = model.medium

                for ingredient in medium:
                    if ingredient not in uptakes:
                        medium[ingredient] = 0.0

                model.medium = medium
                if reaction in model.reactions:
                    constraint = model.problem.Constraint(model.reactions.get_by_id(reaction).flux_expression,
                                                          lb=0.001, ub=100)
                    model.add_cons_vars(constraint)
                    try:
                        solution = model.optimize()
                        if solution.fluxes[reaction] > 0.0 and \
                                solution.objective_value is not None and solution.objective_value > 0.09:
                            value = 1
                            print(reaction, solution.fluxes[reaction])
                    except (UserWarning, OptimizationError):
                        value = 0
                # else:
                #     print(reaction, "not found in microbe's genome.")

        group_test = pd.DataFrame([value], index=[explored_group])
        group_test.columns = [name]
        microbe_boolean_table = pd.concat([microbe_boolean_table, group_test])

    microbe_boolean_table = microbe_boolean_table.transpose()
    production_boolean_table = pd.concat([production_boolean_table, microbe_boolean_table])

production_boolean_table.to_csv(path_out + output_folder + 'compilation/production_compilation.csv')

g = sns.clustermap(production_boolean_table, cmap="YlGnBu", cbar_pos=None, col_cluster=False, figsize=(75, 200),
                   dendrogram_ratio=(.1, .2))
g.savefig(path_out + output_folder + 'graphs/production_compilation.jpeg')

reordered = g.data2d
reordered.to_csv(path_out + output_folder + 'compilation/production_compilation_reordered.csv')

outcome_dict = {}

for index, row in enumerate(reordered.iterrows()):
    microbe = row[0]
    outcome_list = []
    for number in range(len(reordered.columns)):
        result = reordered.iloc[index][reordered.columns[number]]
        if result > 0:
            product = reordered.columns[number]
            outcome_list.append(product)
        else:
            outcome_list.append(0)
    outcome_dict.update({microbe: outcome_list})

outcome_table = pd.DataFrame.from_dict(outcome_dict, orient='index')
outcome_table.columns = reordered.columns
# outcome_table = outcome_table.drop(['Cluster'], axis=1)
outcome_table.to_csv(
    path_out + output_folder + 'compilation/production_compilation_reordered_nutrient_name.csv')

final_production_ruleset = {}

for index, row in outcome_table.iterrows():
    produced_nutrients = []
    for value in row:
        if value != 0 and value != '0':
            produced_nutrients.append(value)
    nutrient_set = ''
    for nutrient in produced_nutrients:
        nutrient_set = nutrient_set + nutrient + ','
    nutrient_set = '(' + nutrient_set[:-1] + ')'
    if nutrient_set not in final_production_ruleset:
        final_production_ruleset.update({nutrient_set: [index]})
    else:
        final_production_ruleset[nutrient_set].append(index)

with open(path_out + output_folder + 'cluster/production_by_nutrient_set.txt', 'w') as file:
    for combination in final_production_ruleset:
        inner_cluster = final_production_ruleset[combination]
        line = combination + ': ' + str(inner_cluster) + '\n\n'
        file.write(line)

with open(path_out + output_folder + 'cluster/_production_by_nutrient_set_len.txt', 'w') as file:
    for combination in final_production_ruleset:
        inner_cluster = final_production_ruleset[combination]
        line = combination + ': ' + str(len(inner_cluster)) + '\n\n'
        file.write(line)
        line = '\n\n'

with open(path_out + output_folder + 'cluster/_experimental_design.txt', 'w') as file:
    file.write('This results were generated using the nutrient_secretion_aa_vit.py script')
    line = '\n\n'
    file.write(str(rich_media_no_explored_n))