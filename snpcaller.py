# -*- coding: utf-8 -*-

import pandas as pd
import pysam
import numpy as np
import argparse

"""Read in BAM file and putative snps file"""

# Define command-line arguments
parser = argparse.ArgumentParser(description='Process BAM file and SNP file.')
parser.add_argument('bamfile', help='Path to BAM file')
parser.add_argument('snpfile', help='Path to SNP file')

# Parse command-line arguments
args = parser.parse_args()

# Open the BAM file using PySam
bamfile = pysam.AlignmentFile(args.bamfile, "rb")

# Read the putative snp file using Pandas
snpfile = pd.read_csv(args.snpfile, sep='\t')

'''
# Open the BAM file using PySam, make sure you have an index file for your BAM or make one 
bamfile = pysam.AlignmentFile("/content/align_sort.bam", "rb")
#bamfile_idx = pysam.AlignmentFile("/content/align_sort.bam.bai", "rb")


# Read the putative snp file using Pandas
snpfile = pd.read_csv("/content/putatative_snps.tsv", sep='\t')
'''

# Initialize empty list to store information
data = []

for index, row in snpfile.iterrows():
    chrom = row["chr"]
    pos = int(row["pos"])
    ref = row["ref"]
    alt = row["alt"]
    maf = float(row["maf"])

    # Calculate the prior probabilities
    ref_prior = (1 - maf) ** 2
    alt_prior = maf ** 2
    het_prior = 1 - alt_prior - ref_prior

    # initialize allele count
    ref_count = 0
    alt_count = 0

    # Find overlapping reads
    overlapping_reads = list(bamfile.fetch(chrom, pos-1, pos))

    for pileupcolumn in bamfile.pileup(chrom, pos-1, pos):
        if pileupcolumn.pos == pos-1:
            # iterate through each read at the SNP position
            for pileupread in pileupcolumn.pileups:
                # check if read supports alternate allele
                if pileupread.alignment.query_sequence[pileupread.query_position] == alt:
                    alt_count += 1
                # check if read supports reference allele
                elif pileupread.alignment.query_sequence[pileupread.query_position] == ref:
                    ref_count += 1

                    # calculate quality score and P_error for the SNP position
                    quality_scores = pileupread.alignment.query_qualities
                    quality_score = quality_scores[pileupread.query_position]
                    p_error = 10 ** (-quality_score/10.0)


    # Append information to data list
    data.append({
        "chrom": chrom,
        "pos": pos,
        "ref": ref,
        "alt": alt,
        "maf": maf,
        "ref_prior": ref_prior,
        "alt_prior": alt_prior,
        "het_prior": het_prior,
        "overlap_count" : len(overlapping_reads),
        "ref_count": ref_count,
        "alt_count": alt_count,
        "quality_score": quality_score,
        "p_error": p_error
    })

# Create pandas DataFrame from data list
result_df = pd.DataFrame(data)

# Print result DataFrame
#print(result_df)

# initialize the output data frame
#out_df = pd.DataFrame(columns=['chromosome', 'position', 'putative genotype', 'n reads'])
out_df = pd.DataFrame()
# iterate over each row in the input data frame
for idx, row in result_df.iterrows():

    # get the number of reads for this position
    n_reads = row['overlap_count']

    # initialize likelihoods and posterior probabilities
    ll_ref_ref = ll_alt_alt = ll_ref_alt = 0.0
    pp_ref = pp_alt = pp_ref_alt = 0.0

    # calculate the likelihoods
    # the true allele is the reference allele  
    for i in range(row['ref_count']):
        if row['ref_count'] > row['alt_count']:
            ll_ref_ref += np.log(1 - row['p_error']) #no error in ref
            ll_alt_alt += np.log(row['p_error']) #error in alt
            ll_ref_alt += np.log((1 - row['p_error'])/2 + row['p_error']/2)
            #ll_ref_alt += np.log(1/2)
      
    # the true allele is the alt allele
    for i in range(row['alt_count']):
        ll_alt_alt += np.log(1 - row['p_error']) #no error in alt
        ll_ref_ref += np.log(row['p_error']) #error in ref
        ll_ref_alt += np.log(((1 - row['p_error'])/2) + (row['p_error']/2))
        #ref_alt += np.log(1/2) 
       

    # calculate posterior probabilities for ref and alt alleles
    pp_ref = np.exp(ll_ref_ref + row['ref_prior']) / (np.exp(ll_ref_ref + row['ref_prior']) + np.exp(ll_alt_alt + row['alt_prior']) + np.exp(ll_ref_alt + row['het_prior']))
    pp_alt = np.exp(ll_alt_alt + row['alt_prior']) / (np.exp(ll_ref_ref + row['ref_prior']) + np.exp(ll_alt_alt + row['alt_prior']) + np.exp(ll_ref_alt + row['het_prior']))
    pp_ref_alt = np.exp(ll_ref_alt + row['het_prior'])/ (np.exp(ll_ref_ref + row['ref_prior']) + np.exp(ll_alt_alt + row['alt_prior']) + np.exp(ll_ref_alt + row['het_prior']))

    # determine putative genotype 
    max_pp = max(pp_ref, pp_alt, pp_ref_alt) # find the maximum posterior probability
    if max_pp == pp_ref:
        put_genotype = row['ref'] + row['ref']
    elif max_pp == pp_alt:
        put_genotype = row['alt'] + row['alt']
    else:
        put_genotype = row['ref'] + row['alt']


    # determine putative genotype 
    put_genotype_ref = row['ref'] + row['ref']
    put_genotype_alt = row['alt'] + row['alt']
    put_genotype_ref_alt = row['ref'] + row['alt']


    # add the results to the output DataFrame
    out_df = pd.concat([out_df, pd.DataFrame({
        'chromosome': [row['chrom']],
        'position': [row['pos']],
        'ref_allele': [row['ref']],
        'alt_allele': [row['alt']],
        'putative genotype': [put_genotype],
        'ref posterior probability': [pp_ref],
        'alt posterior probability': [pp_alt],
        'het posterior probability': [pp_ref_alt],
        'n reads': [n_reads]
    })])



#print(out_df)
#output dataframe to tsv file 
out_df.to_csv('output_file.tsv', sep='\t', index=False)

# Close the BAM file
bamfile.close()


