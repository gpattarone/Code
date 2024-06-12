#!/usr/bin/env python3

import argparse
import os
import subprocess

def run_star(fastq_files, reference_genome, gtf, output_dir):
    star_index = os.path.join(output_dir, 'STAR_index')
    os.makedirs(star_index, exist_ok=True)
    
    # Generate STAR index
    subprocess.run([
        'STAR', '--runThreadN', '8', '--runMode', 'genomeGenerate',
        '--genomeDir', star_index, '--genomeFastaFiles', reference_genome,
        '--sjdbGTFfile', gtf, '--sjdbOverhang', '100'
    ])
    
    # Align reads
    for fastq_file in fastq_files:
        output_prefix = os.path.join(output_dir, os.path.basename(fastq_file).split('.')[0])
        subprocess.run([
            'STAR', '--runThreadN', '8', '--genomeDir', star_index,
            '--readFilesIn', fastq_file, '--outFileNamePrefix', output_prefix,
            '--outSAMtype', 'BAM', 'SortedByCoordinate'
        ])

def run_rsem(fastq_files, reference_genome, gtf, output_dir):
    rsem_ref = os.path.join(output_dir, 'RSEM_reference')
    os.makedirs(rsem_ref, exist_ok=True)
    
    # Prepare RSEM reference
    subprocess.run([
        'rsem-prepare-reference', '--gtf', gtf, reference_genome, rsem_ref
    ])
    
    # Run RSEM
    for fastq_file in fastq_files:
        output_prefix = os.path.join(output_dir, os.path.basename(fastq_file).split('.')[0])
        subprocess.run([
            'rsem-calculate-expression', '--star', '--paired-end',
            '--output-genome-bam', '--alignments', fastq_file,
            rsem_ref, output_prefix
        ])

def run_variant_analysis(bam_files, reference_genome, output_dir):
    for bam_file in bam_files:
        # Step 1: Mark duplicates
        dedup_bam_file = bam_file.replace('.bam', '.dedup.bam')
        metrics_file = bam_file.replace('.bam', '.metrics.txt')
        subprocess.run([
            'gatk', 'MarkDuplicates', '-I', bam_file, '-O', dedup_bam_file, '-M', metrics_file
        ])
        
        # Step 2: Index the deduplicated BAM file
        subprocess.run(['samtools', 'index', dedup_bam_file])
        
        # Step 3: Call variants using GATK HaplotypeCaller
        vcf_file = dedup_bam_file.replace('.bam', '.vcf')
        subprocess.run([
            'gatk', 'HaplotypeCaller', '-R', reference_genome, '-I', dedup_bam_file, '-O', vcf_file
        ])
        
        # Optional: Step 4: Filter the VCF file
        filtered_vcf_file = vcf_file.replace('.vcf', '.filtered.vcf')
        subprocess.run([
            'gatk', 'VariantFiltration', '-R', reference_genome, '-V', vcf_file, '-O', filtered_vcf_file,
            '--filter-expression', 'QD < 2.0 || FS > 60.0 || MQ < 40.0', '--filter-name', 'basic_snp_filter'
        ])

def main():
    parser = argparse.ArgumentParser(description="RNA-seq analysis pipeline")
    parser.add_argument('--fastq', nargs='+', required=True, help='List of FASTQ files')
    parser.add_argument('--reference', required=True, help='Reference genome FASTA file')
    parser.add_argument('--gtf', required=True, help='GTF annotation file')
    parser.add_argument('--output', required=True, help='Output directory')
    
    args = parser.parse_args()
    
    fastq_files = args.fastq
    reference_genome = args.reference
    gtf = args.gtf
    output_dir = args.output
    
    os.makedirs(output_dir, exist_ok=True)
    
    run_star(fastq_files, reference_genome, gtf, output_dir)
    run_rsem(fastq_files, reference_genome, gtf, output_dir)
    
    bam_files = [os.path.join(output_dir, os.path.basename(f).split('.')[0] + 'Aligned.sortedByCoord.out.bam') for f in fastq_files]
    run_variant_analysis(bam_files, reference_genome, output_dir)

if __name__ == "__main__":
    main()